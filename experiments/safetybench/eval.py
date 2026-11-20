"""Cross-dataset check: run the MCPTox-trained detectors on MCP-SafetyBench poison.

MCP-SafetyBench (arXiv 2512.15163, github xjzzzzzzzz/MCPSafety) is an independent MCP
safety benchmark. Most of its attacks live in the user query (prompt injection), but its
"Tool Poisoning-*" tasks put the attack in a **tool description** -- exactly what our
detectors inspect. This script extracts those poisoned descriptions from a local clone
(reading JSON only; it runs no code from the download) and measures each detector's
recall (fraction blocked) on this out-of-distribution set.

    git clone --depth 1 https://github.com/xjzzzzzzzz/MCPSafety.git <dir>   # done once, outside the repo
    python experiments/safetybench/eval.py --safetybench-dir <dir> --ckpt-root checkpoints/mcp_guard

The benchmark data is NOT vendored here (external, no license file); point --safetybench-dir
at your own clone.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root, so `attacker` imports

DETECTORS = ["frozen_mcpguard", "mcpguard_full", "mcpguard_head",
             "e5base_full", "e5base_head", "mcp_guardian"]


def extract_poisoned(sb_dir: str) -> list[dict]:
    """Every poisoned tool description in the benchmark's Tool-Poisoning tasks.

    They sit in ``mcp_server_modifications[].modification_description`` of the task
    configs. Pure JSON reads -- no code from the download is executed."""
    rows = []
    for f in glob.glob(str(Path(sb_dir) / "mcpuniverse/benchmark/configs/**/*.json"), recursive=True):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        for m in (d.get("mcp_server_modifications") or []):
            desc = (m.get("modification_description") or "").strip()
            if desc:
                rows.append({"tool_name": m.get("tool_name", ""), "description": desc,
                             "attack_category": d.get("attack_category")})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--safetybench-dir", required=True, help="path to a local MCP-SafetyBench clone")
    ap.add_argument("--ckpt-root", default="checkpoints/mcp_guard")
    ap.add_argument("--out", default=None, help="optional CSV path for the per-detector recall")
    args = ap.parse_args()

    from attacker.detectors import build

    rows = extract_poisoned(args.safetybench_dir)
    n = len(rows)
    print(f"MCP-SafetyBench poisoned tool descriptions: {n}\n")

    overall, bysub = {}, defaultdict(lambda: defaultdict(lambda: [0, 0]))
    print(f"{'detector':18s} recall (blocked / {n})")
    for key in DETECTORS:
        det = build(key, args.ckpt_root)
        blocked = 0
        for r in rows:
            b = bool(det.check(r["tool_name"], r["description"]).blocked)
            blocked += b
            sub = (r["attack_category"] or "").replace("Tool Poisoning-", "")
            bysub[key][sub][0] += b
            bysub[key][sub][1] += 1
        overall[key] = blocked
        print(f"{key:18s} {blocked:3d}/{n} = {100*blocked/n:.1f}%")
        del det

    print("\nper-subtype recall (mcpguard_full):")
    for sub, (x, c) in sorted(bysub["mcpguard_full"].items(), key=lambda k: -k[1][1]):
        print(f"  {sub:30s} {x:2d}/{c:2d} = {100*x/c:.0f}%")

    if args.out:
        lines = ["detector,blocked,total,recall"]
        lines += [f"{k},{v},{n},{v/n:.4f}" for k, v in overall.items()]
        Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
