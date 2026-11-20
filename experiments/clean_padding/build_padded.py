"""Build the length-matched clean variant datasets from Claude-authored rewordings.

Merges local_eval/rw/*.json ({index: padded_text}), maps each index to its case_id via
local_eval/to_reword.json, and writes data/processed/<split>_cleanpadded.jsonl where every
clean description originally <170 chars is replaced by its padded version (meaning preserved).
Poisoned rows and clean rows >=170 are copied unchanged. Runs a benign regex check on every
padded description and writes report/clean_padding_report.csv. Originals are never modified.
"""

from __future__ import annotations

import csv
import glob
import json
import re
from pathlib import Path

PROC = Path("MCP-PROBE/data/processed")
RW = Path("local_eval/rw")
TODO = Path("local_eval/to_reword.json")
REPORT = Path("report/clean_padding_report.csv")
BAD = re.compile(r"(ignore (the )?previous|<important>|you must first|~/\.ssh|/etc/passwd|id_rsa|"
                 r"https?://|\bbcc\b|exfiltrat|system prompt|delete email|redirect)", re.I)


def main():
    items = json.loads(TODO.read_text(encoding="utf-8"))
    padded = {}
    for f in sorted(glob.glob(str(RW / "*.json"))):
        padded.update({int(k): v for k, v in json.loads(Path(f).read_text(encoding="utf-8")).items()})
    missing = [i for i in range(len(items)) if i not in padded]
    assert not missing, f"missing rewordings for indices: {missing[:10]} (total {len(missing)})"

    by_case = {}
    for idx, it in enumerate(items):
        new = " ".join(padded[idx].split())
        status = "flagged_bad_content" if BAD.search(new) else ("too_short" if len(new) <= it["orig_len"] else "ok")
        by_case[it["case_id"]] = {**it, "padded": new, "new_len": len(new), "status": status}

    REPORT.parent.mkdir(exist_ok=True)
    rep = csv.writer(REPORT.open("w", newline="", encoding="utf-8-sig"))
    rep.writerow(["case_id", "split", "server", "orig_len", "target_len", "new_len", "status", "orig", "padded"])
    n_pad = flagged = short = 0
    before, after = [], []
    for split in ("tune", "val", "test"):
        rows = [json.loads(l) for l in (PROC / f"{split}.jsonl").open(encoding="utf-8")]
        out = PROC / f"{split}_cleanpadded.jsonl"
        with out.open("w", encoding="utf-8") as fh:
            for r in rows:
                d = by_case.get(r["case_id"])
                if d and d["status"] == "ok":
                    before.append(d["orig_len"]); after.append(d["new_len"]); n_pad += 1
                    r = {**r, "description": d["padded"], "orig_description": d["orig"],
                         "padded": True, "orig_len": d["orig_len"], "new_len": d["new_len"]}
                else:
                    r = {**r, "padded": False}
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        for cid, d in by_case.items():
            if d["split"] == split:
                rep.writerow([d["case_id"], d["split"], d["server"], d["orig_len"], d["target_len"],
                              d["new_len"], d["status"], d["orig"], d["padded"]])
                flagged += d["status"] == "flagged_bad_content"
                short += d["status"] == "too_short"

    def q(a, p):
        a = sorted(a); return a[int(p * (len(a) - 1))]
    print(f"padded {n_pad} clean tools (<170 chars) across tune+val+test")
    print(f"flagged_bad_content={flagged}  too_short={short}")
    print(f"length BEFORE: min={min(before)} median={q(before,.5)} max={max(before)}")
    print(f"length AFTER : min={min(after)} median={q(after,.5)} max={max(after)}  (attack median ~247)")
    print(f"variant files: {', '.join(str(PROC/f'{s}_cleanpadded.jsonl') for s in ('tune','val','test'))}")
    print(f"report: {REPORT}")
    print("BUILD_DONE")


if __name__ == "__main__":
    main()
