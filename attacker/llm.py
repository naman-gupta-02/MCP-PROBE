"""OpenAI-compatible chat client for the attacker and the judges (Groq by default).

Groq's free plan has per-model limits on requests and tokens per minute and per day
(console.groq.com/docs/rate-limits; exact numbers are on each account's /settings/limits).
The client spaces calls to stay under the per-minute limits, waits out HTTP 429s using the
server's retry-after, and stops cleanly with DailyLimitReached when a daily limit is hit, so a
run can be resumed the next day.

StubLLM answers from a function, for tests and dry runs without an API key.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests

ROOT = Path(__file__).resolve().parents[1]


class DailyLimitReached(RuntimeError):
    """The provider refused a call because a per-day request or token limit is used up."""


@dataclass
class ChatResult:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env reader (KEY=value lines); existing environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


class MinuteBudget:
    """Sliding 60 s window over requests and tokens; wait() blocks until a call fits."""

    def __init__(self, rpm: int | None, tpm: int | None, clock=time.monotonic, sleep=time.sleep):
        self.rpm, self.tpm = rpm, tpm
        self.clock, self.sleep = clock, sleep
        self.calls: deque[tuple[float, int]] = deque()

    def _trim(self, now: float) -> None:
        while self.calls and now - self.calls[0][0] >= 60:
            self.calls.popleft()

    def wait(self, tokens: int) -> None:
        while True:
            now = self.clock()
            self._trim(now)
            used = sum(t for _, t in self.calls)
            if (self.rpm is None or len(self.calls) < self.rpm) and (self.tpm is None or used + tokens <= self.tpm or not self.calls):
                return
            self.sleep(max(0.05, 60 - (now - self.calls[0][0])))

    def record(self, tokens: int) -> None:
        self.calls.append((self.clock(), tokens))


class ChatClient:
    def __init__(
        self,
        model: str,
        base_url: str = "https://api.groq.com/openai/v1",
        api_key_env: str = "GROQ_API_KEY",
        api_keys_env: str = "GROQ_API_KEYS",
        keys: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        rpm: int | None = None,
        tpm: int | None = None,
        timeout_s: float = 120.0,
        max_retries: int = 10,
        extra_body: dict | None = None,
    ):
        load_dotenv()
        if keys is None:
            # Prefer a comma-separated GROQ_API_KEYS; fall back to the single GROQ_API_KEY.
            multi = os.environ.get(api_keys_env, "")
            keys = [k.strip() for k in multi.split(",") if k.strip()]
            if not keys and os.environ.get(api_key_env):
                keys = [os.environ[api_key_env].strip()]
        if not keys:
            raise ValueError(f"no key: set {api_keys_env} or {api_key_env} in .env (gitignored) or the environment")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.keys = keys
        # Stagger which key each model starts on, so several clients spread load instead of all
        # hammering key 1 first. Stable across runs (not the salted built-in hash).
        self.idx = int(hashlib.sha1(model.encode()).hexdigest(), 16) % len(keys)
        self.exhausted: set[int] = set()
        self._hops = 0  # consecutive per-minute-429 key hops since the last success
        self.budgets = [MinuteBudget(rpm, tpm) for _ in keys]  # per-key minute budget
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.extra_body = extra_body or {}

    @property
    def key_count(self) -> int:
        return len(self.keys)

    def _live_count(self) -> int:
        return len(self.keys) - len(self.exhausted)

    def _next_live(self) -> int | None:
        """The next key not daily-exhausted, round-robin from the current one (None if none)."""
        for step in range(1, len(self.keys) + 1):
            j = (self.idx + step) % len(self.keys)
            if j not in self.exhausted:
                return j
        return None

    def _rotate_after_daily(self) -> None:
        """Mark the current key spent and move to the next one; raise once all are spent."""
        self.exhausted.add(self.idx)
        nxt = self._next_live()
        if nxt is None:
            raise DailyLimitReached(f"{self.model}: all {len(self.keys)} key(s) hit a daily limit")
        self.idx = nxt

    def chat(self, messages: list[dict], temperature: float | None = None, max_tokens: int | None = None) -> ChatResult:
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": max_tokens or self.max_tokens,
            **self.extra_body,
        }
        est = sum(len(m["content"]) for m in messages) // 4 + body["max_tokens"]  # rough token estimate
        last = ""
        retry = 0
        while True:
            budget = self.budgets[self.idx]
            budget.wait(est)
            headers = {"Authorization": f"Bearer {self.keys[self.idx]}", "Content-Type": "application/json"}
            t0 = time.perf_counter()
            sleep_for = None
            try:
                r = requests.post(f"{self.base_url}/chat/completions", json=body, headers=headers, timeout=self.timeout_s)
            except requests.RequestException as e:
                last, sleep_for = str(e), 2 ** retry
            else:
                if r.status_code == 429:
                    budget.record(est)
                    if _is_daily(r):
                        self._rotate_after_daily()  # raises DailyLimitReached once every key is spent
                        retry, self._hops = 0, 0  # fresh key -> fresh backoff
                        continue
                    # Per-minute limit: hop to another live key for a full cycle before backing off,
                    # so 5 keys give ~5x the per-minute budget instead of waiting on one.
                    last = "HTTP 429"
                    nxt = self._next_live()
                    if nxt is not None and self._hops < self._live_count():
                        self.idx, self._hops = nxt, self._hops + 1
                        time.sleep(0.2)
                        continue
                    self._hops = 0  # all live keys rate-limited this cycle -> wait it out
                    if nxt is not None:
                        self.idx = nxt
                    sleep_for = _retry_after(r, 2 ** retry)
                elif r.status_code >= 500:
                    last, sleep_for = f"HTTP {r.status_code}", 2 ** retry
                else:
                    r.raise_for_status()
                    j = r.json()
                    usage = j.get("usage") or {}
                    budget.record(usage.get("total_tokens") or est)
                    self._hops = 0
                    return ChatResult(
                        text=j["choices"][0]["message"].get("content") or "",
                        model=self.model,
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                        latency_ms=(time.perf_counter() - t0) * 1000,
                    )
            retry += 1
            if retry >= self.max_retries:
                raise RuntimeError(f"{self.model}: gave up after {retry} attempts ({last})")
            time.sleep(sleep_for)


def _retry_after(r: requests.Response, default: float) -> float:
    v = r.headers.get("retry-after")
    try:
        return float(v) + 0.5 if v else default
    except ValueError:
        return default


def _is_daily(r: requests.Response) -> bool:
    """Groq names the exhausted limit in the error message, e.g. 'tokens per day (TPD)'."""
    msg = r.text.lower()
    return "per day" in msg or "(rpd)" in msg or "(tpd)" in msg


class StubLLM:
    """Deterministic stand-in: respond(messages) -> text. Counts calls."""

    def __init__(self, respond: Callable[[list[dict]], str], model: str = "stub"):
        self.respond = respond
        self.model = model
        self.calls = 0

    def chat(self, messages: list[dict], temperature: float | None = None, max_tokens: int | None = None) -> ChatResult:
        self.calls += 1
        return ChatResult(text=self.respond(messages), model=self.model)
