# Clean-tool length padding

Clean MCPTox tool descriptions are far shorter than poisoned ones (dev median 46 vs 247 chars),
so a detector could exploit length instead of content. This pads **only** clean descriptions
shorter than 170 characters, rewriting each longer while preserving its exact action and meaning
and adding only benign, truthful detail (inputs, outputs, usage), in the original language.
Target lengths are drawn from the dev poisoned length distribution. Clean tools >=170 chars and
all poisoned rows are left unchanged. Originals are never modified.

- `rw/batch_*.json` — the expanded descriptions, keyed by index into `to_reword.json` (hand-authored, meaning-preserving).
- `to_reword.json` — the 222 clean tools <170 chars (tune 166, val 23, test 33) with sampled target lengths.
- `build_padded.py` — merges the rewordings and writes `data/processed/{tune,val,test}_cleanpadded.jsonl` + the report.
- `pad_clean_tools.py` — the earlier LLM-driven variant (superseded by the hand-authored rewordings).
- `clean_tools_all_padded.csv` — all 316 clean tools (222 padded): split, server, tool, orig/final length, both texts.
- `clean_padding_report.csv` — per-padded-tool record with status and before/after text.

Result: clean median length 46 -> 294 (attack median 247); clean tools <=100 chars 65% -> 1%;
0 of 222 padded descriptions introduce a new MCP Guardian flag; poisoned rows untouched.

Variant files are opt-in: experiments load `*_cleanpadded.jsonl` instead of the originals.
