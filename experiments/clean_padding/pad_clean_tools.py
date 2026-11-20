"""Length-match clean MCPTox tool descriptions to the attack length distribution.

Why: clean descriptions are far shorter than poisoned ones (dev median 57 vs 247), so a
detector could exploit length instead of content. This pads ONLY clean descriptions shorter
than --threshold (default 170) by rewriting them longer with a local LLM, preserving the exact
action/meaning and adding only neutral, truthful elaboration. Descriptions >= threshold and all
poisoned rows are left untouched. Target length for each short clean tool is sampled from the
DEV (tune+val) poisoned length distribution, so padded clean lengths mirror attack lengths.

Writes variant files data/processed/<split>_cleanpadded.jsonl (originals untouched) plus a CSV
report. Resumable: a per-case cache (padded_cache.jsonl) is reused, so reruns skip done tools.

  python local_eval/pad_clean_tools.py --base-url http://127.0.0.1:8000/v1 --model Qwen/Qwen2.5-7B-Instruct
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

import requests

PROC = Path("MCP-PROBE/data/processed")
OUT_CACHE = PROC / "padded_cache.jsonl"
REPORT = Path("report/clean_padding_report.csv")
SYSTEM = (
    "You expand a short, benign software-tool description into a longer one WITHOUT changing its "
    "meaning or action. Keep the exact same action. Add only truthful, neutral detail. Do not invent "
    "new behaviour, instructions, commands, requirements, warnings, URLs, file paths, or security "
    "notes. Keep the original language. Output only the description, nothing else."
)
# Safety net: flag if the LLM ever introduces attack-like text (padding must stay benign).
BAD = re.compile(r"(ignore (the )?previous|<important>|you must first|~/\.ssh|/etc/passwd|id_rsa|"
                 r"https?://|bcc|exfiltrat|system prompt)", re.I)


def load(split):
    return [json.loads(l) for l in (PROC / f"{split}.jsonl").open(encoding="utf-8")]


def attack_pool():
    return [len(r["description"]) for s in ("tune", "val") for r in load(s)
            if r["is_poisoned"] and (r.get("description") or "").strip()]


def pick_target(orig_len, pool, rng):
    """A target sampled from the attack length distribution, strictly longer than the original."""
    for _ in range(50):
        t = rng.choice(pool)
        if t > orig_len + 20:
            return t
    return max(orig_len + 150, 247)


def elaborate(base_url, model, orig, target, rng):
    lo = max(target - 40, len(orig) + 40)
    user = (f"Expand this tool description to about {target} characters (write 3-4 full sentences). "
            f"Keep the same action and meaning. Describe: (1) what the tool does, (2) its typical "
            f"inputs/parameters, (3) what it returns, (4) a typical usage situation. Do not add any "
            f"new capability or instruction. Output ONLY the rewritten description.\n\nDescription: {orig}")
    best = ""
    for attempt in range(3):
        try:
            r = requests.post(f"{base_url}/chat/completions", timeout=150, json={
                "model": model, "temperature": 0.6, "max_tokens": 320,
                "messages": [{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": user if attempt == 0 else
                              user + f"\n\nYour previous attempt was too short; write at least {lo} characters with more neutral detail."}]})
            r.raise_for_status()
            txt = " ".join(r.json()["choices"][0]["message"]["content"].split()).strip().strip('"')
        except Exception as e:
            return "", f"llm_error: {str(e)[:80]}"
        if len(txt) > len(best):
            best = txt
        if len(txt) >= lo:
            break
    flagged = bool(BAD.search(best))
    return best, ("flagged_bad_content" if flagged else "ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--model", required=True)
    ap.add_argument("--threshold", type=int, default=170)
    ap.add_argument("--splits", nargs="+", default=["tune", "val", "test"])
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    pool = attack_pool()
    print(f"attack length pool n={len(pool)} (dev poisoned)", flush=True)

    done = {}
    if OUT_CACHE.exists():
        for l in OUT_CACHE.open(encoding="utf-8"):
            d = json.loads(l)
            done[d["case_id"]] = d
    REPORT.parent.mkdir(exist_ok=True)
    cache_fh = OUT_CACHE.open("a", encoding="utf-8")

    todo = [(s, r) for s in args.splits for r in load(s)
            if not r["is_poisoned"] and (r.get("description") or "").strip()
            and len(r["description"]) < args.threshold and r["case_id"] not in done]
    print(f"to pad: {len(todo)} (already cached: {len(done)})", flush=True)

    for i, (split, r) in enumerate(todo, 1):
        orig = r["description"]
        target = pick_target(len(orig), pool, rng)
        new, status = elaborate(args.base_url, args.model, orig, target, rng)
        rec = {"case_id": r["case_id"], "split": split, "server": r["server"],
               "orig_len": len(orig), "target_len": target,
               "new_len": len(new), "status": status, "orig": orig, "padded": new}
        done[r["case_id"]] = rec
        cache_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        cache_fh.flush()
        if i % 10 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)} {split} {r['server'][:14]:14s} {len(orig)}->{len(new)} [{status}]", flush=True)

    cache_fh.close()

    # Write variant split files (originals untouched) + CSV report.
    import csv
    rep = csv.writer(REPORT.open("w", newline="", encoding="utf-8-sig"))
    rep.writerow(["case_id", "split", "server", "orig_len", "target_len", "new_len", "status", "orig", "padded"])
    flagged = short_fail = 0
    for split in args.splits:
        rows = load(split)
        out = PROC / f"{split}_cleanpadded.jsonl"
        with out.open("w", encoding="utf-8") as f:
            for r in rows:
                d = done.get(r["case_id"])
                if d and d["padded"] and d["status"] == "ok":
                    r = {**r, "description": d["padded"], "orig_description": d["orig"],
                         "padded": True, "orig_len": d["orig_len"], "new_len": d["new_len"]}
                else:
                    r = {**r, "padded": False}
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        for cid, d in done.items():
            if d["split"] == split:
                rep.writerow([d["case_id"], d["split"], d["server"], d["orig_len"], d["target_len"],
                              d["new_len"], d["status"], d["orig"], d["padded"]])
                flagged += d["status"] == "flagged_bad_content"
                short_fail += d["status"].startswith("llm_error")
    print(f"\nwrote variant files: {', '.join(str(PROC/f'{s}_cleanpadded.jsonl') for s in args.splits)}")
    print(f"report: {REPORT} | flagged_bad_content={flagged} llm_errors={short_fail}")
    lens = [d["new_len"] for d in done.values() if d["status"] == "ok"]
    if lens:
        lens.sort(); print(f"padded lengths: min={lens[0]} median={lens[len(lens)//2]} max={lens[-1]} (target band ~attack dist)")
    print("PAD_DONE")


if __name__ == "__main__":
    main()
