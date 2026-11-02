"""The rewrite step: wiring that drives the team's rewrite prompt and parses one candidate out.

This file contains NO rewrite instructions. PromptedAttacker loads the system prompt from a file
you provide (default attacker/rewrite_prompt.txt) and assembles the harness inputs into the user
turn; the creative content is entirely in that file. If the file is missing, it raises with a
pointer, so the harness never ships an attacker prompt of its own.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROMPT = ROOT / "attacker" / "rewrite_prompt.txt"


@dataclass
class RewriteTask:
    """The fixed, per-case context handed to every rewrite in a trajectory."""
    case_id: str
    tool_name: str
    original_description: str
    tool_context: str = ""
    length_target: int | None = None
    length_tolerance: int | None = None


def extract_candidate(text: str | None) -> str | None:
    """Pull {"candidate": "..."} out of a model reply, tolerating think-blocks, fences and preamble.

    Returns the candidate string, or None if nothing parseable is found (a failed attempt)."""
    if not text:
        return None
    t = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I).strip()
    for chunk in _json_chunks(t):
        try:
            obj = json.loads(chunk, strict=False)  # strict=False tolerates raw newlines/tabs in the string
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict) and isinstance(obj.get("candidate"), str):
            return obj["candidate"].strip() or None
    return None


def _json_chunks(t: str):
    yield t  # the whole reply, if it is bare JSON
    for m in re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", t, flags=re.S):  # fenced
        yield m
    for m in re.findall(r"\{[^{}]*\"candidate\"[^{}]*\}", t, flags=re.S):  # a tight object
        yield m
    braces = re.findall(r"\{.*\}", t, flags=re.S)  # outermost span, last resort
    if braces:
        yield braces[-1]


def build_user_message(task: RewriteTask, current: str, attempt: int, feedback: dict,
                       previous: list[str]) -> str:
    """Assemble the harness data for the user turn. Labels only — no rewrite guidance here."""
    parts = [
        f"tool_name: {task.tool_name}",
        f"attempt: {attempt}",
        f"original_description:\n{task.original_description}",
        f"current_description:\n{current}",
    ]
    if task.tool_context:
        parts.append(f"tool_context:\n{task.tool_context}")
    if task.length_target is not None:
        tol = "" if task.length_tolerance is None else f" (tolerance {task.length_tolerance})"
        parts.append(f"length_target: {task.length_target} words{tol}")
    if previous:
        shown = previous[-2:]  # keep the prompt bounded
        parts.append("previous_attempts:\n" + "\n---\n".join(shown))
    if feedback:
        parts.append("detector_feedback (data):\n" + json.dumps(feedback))
    return "\n\n".join(parts)


class PromptedAttacker:
    """Implements the Attacker protocol by calling an LLM with the team-supplied rewrite prompt."""

    def __init__(self, client, prompt_path: str | Path = DEFAULT_PROMPT,
                 temperature: float = 0.9, max_tokens: int = 1500):
        p = Path(prompt_path)
        if not p.is_file():
            raise FileNotFoundError(
                f"rewrite prompt not found at {p}. Put your attacker system prompt there; the harness "
                "does not ship one. Everything else (loop, parsing, judging, metrics) is ready."
            )
        self.system = p.read_text(encoding="utf-8").strip()
        if not self.system:
            raise ValueError(f"{p} is empty; add your attacker system prompt")
        self.client = client
        self.model = getattr(client, "model", "?")
        self.temperature = temperature
        self.max_tokens = max_tokens

    def rewrite(self, task: RewriteTask, current: str, attempt: int, feedback: dict,
                previous: list[str]) -> str | None:
        messages = [
            {"role": "system", "content": self.system},
            {"role": "user", "content": build_user_message(task, current, attempt, feedback, previous)},
        ]
        res = self.client.chat(messages, temperature=self.temperature, max_tokens=self.max_tokens)
        return extract_candidate(res.text)
