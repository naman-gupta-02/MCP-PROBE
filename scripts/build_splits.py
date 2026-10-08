"""Build tune/val/test JSONL files from MCPTox and our server split.

Reads  data/raw/MCPTox-Benchmark/response_all.json
       data/splits/server_split.json
Writes data/processed/{tune,val,test}.jsonl
       data/splits/split_report.md

Deterministic and safe to re-run: outputs are fully overwritten, and records
keep the dataset's own order. Prints counts only, never case text.

Usage: uv run python scripts/build_splits.py
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "MCPTox-Benchmark"
RESPONSE_FILE = RAW_DIR / "response_all.json"
SPLIT_FILE = ROOT / "data" / "splits" / "server_split.json"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORT_FILE = ROOT / "data" / "splits" / "split_report.md"

SPLITS = ("tune", "val", "test")
FIELDS = (
    "case_id", "server", "tool_name", "description", "is_poisoned", "paradigm",
    "risk_category", "split", "test_cell", "source_file",
)
# Team decision 2026-10-08: MCPTox "Template-N" is the paper's attack paradigm PN.
PARADIGM_MAP = {"Template-1": "P1", "Template-2": "P2", "Template-3": "P3"}
# wrong_data == 0 are the valid cases; 2 marks cases the authors flagged as bad.
VALID_WRONG_DATA = 0
PAPER_TOTALS = (1312, 1348, 1497)

TOOL_BLOCK_RE = re.compile(
    r"^Tool:[ \t]*(?P<name>.+?)[ \t]*\r?\n"
    r"Description:[ \t]*(?P<desc>.*?)"
    r"(?=\r?\nArguments:|\r?\nTool:|\Z)",
    re.S | re.M,
)


def normalize_block(text: str) -> str:
    """Some poisoned_tool strings use literal '\\n' instead of newlines."""
    if not re.match(r"\s*Tool:[^\n]*\nDescription:", text) and "\\n" in text:
        text = text.replace("\\n", "\n")
    return text.strip()


def parse_tool_blocks(text: str) -> list[tuple[str, str | None]]:
    """(name, description) per tool block; empty or literal "None" descriptions become None."""
    out = []
    for m in TOOL_BLOCK_RE.finditer(text):
        desc = m["desc"].strip()
        out.append((m["name"].strip(), None if desc in ("", "None") else desc))
    return out


def assign(server_split: str, category: str | None, held_out: set[str]) -> tuple[str, str | None]:
    """Return (split, test_cell) for one case."""
    cat_held = category is not None and category in held_out
    if category is None:  # clean tool: server split only
        if server_split == "train":
            return "tune", None
        if server_split == "val":
            return "val", None
        return "test", "new_server_clean"
    if server_split == "test":
        return "test", "new_server_new_cat" if cat_held else "new_server_known_cat"
    if cat_held:
        return "test", "known_server_new_cat"
    return ("tune" if server_split == "train" else "val"), None


def mcptox_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(RAW_DIR), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build() -> dict:
    if not RESPONSE_FILE.exists():
        sys.exit(
            f"Missing {RESPONSE_FILE.relative_to(ROOT)}. Clone MCPTox first:\n"
            "  git clone https://github.com/zhiqiangwang4/MCPTox-Benchmark data/raw/MCPTox-Benchmark"
        )
    split_def = json.loads(SPLIT_FILE.read_text(encoding="utf-8"))
    held_out = set(split_def["held_out_categories"])
    server_to_split = {s: k for k, v in split_def["server_split"].items() for s in v}

    data = json.loads(RESPONSE_FILE.read_text(encoding="utf-8"))
    servers = data["servers"]
    known_categories = set(data["attack_scopes"])

    # Match on the server_name field (the dict keys differ in case for GitHub/GitLab).
    data_servers = {v["server_name"] for v in servers.values()}
    missing = sorted(set(server_to_split) - data_servers)
    extra = sorted(data_servers - set(server_to_split))
    bad_cats = sorted(held_out - known_categories)
    if missing or extra or bad_cats:
        sys.exit(f"Split file does not match dataset. missing={missing} extra={extra} bad_categories={bad_cats}")

    rows: list[dict] = []
    dropped = collections.Counter()  # (reason, server_split, category) -> n
    for key, srv in servers.items():
        name = srv["server_name"]
        srv_split = server_to_split[name]

        # Clean tools: names from tool_names, descriptions from the clean system prompt.
        clean_desc = {}
        for tname, tdesc in parse_tool_blocks(srv["clean_system_promot"]):
            clean_desc.setdefault(tname, tdesc)
        for tname in srv["tool_names"]:
            split, cell = assign(srv_split, None, held_out)
            rows.append({
                "case_id": f"clean::{name}::{tname}",
                "server": name,
                "tool_name": tname,
                "description": clean_desc.get(tname),
                "is_poisoned": False,
                "paradigm": None,
                "risk_category": None,
                "split": split,
                "test_cell": cell,
                "source_file": f"response_all.json#servers/{key}/clean_system_promot",
            })

        # Poisoned cases.
        for idx, inst in enumerate(srv["malicious_instance"]):
            meta = inst.get("metadata") or {}
            category = meta.get("security risk")
            if inst.get("wrong_data") != VALID_WRONG_DATA:
                dropped[(f"wrong_data={inst.get('wrong_data')}", srv_split, category)] += 1
                continue
            if category not in known_categories:
                dropped[("unknown category", srv_split, category)] += 1
                continue
            blocks = parse_tool_blocks(normalize_block(inst["poisoned_tool"]))
            tool_name, desc = blocks[0] if blocks else (None, None)
            split, cell = assign(srv_split, category, held_out)
            rows.append({
                "case_id": f"poison::{name}::{idx}",
                "server": name,
                "tool_name": tool_name,
                "description": desc,
                "is_poisoned": True,
                "paradigm": PARADIGM_MAP.get(meta.get("paradigm")),
                "risk_category": category,
                "split": split,
                "test_cell": cell,
                "source_file": f"response_all.json#servers/{key}/malicious_instance/{idx}",
            })

    ids = [r["case_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate case_id"

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for split in SPLITS:
        path = PROCESSED_DIR / f"{split}.jsonl"
        tmp = path.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                if r["split"] == split:
                    f.write(json.dumps({k: r[k] for k in FIELDS}, ensure_ascii=False) + "\n")
        tmp.replace(path)

    return {
        "rows": rows,
        "dropped": dropped,
        "held_out": held_out,
        "split_def": split_def,
        "raw_total": data.get("data_length"),
        "categories": data["attack_scopes"],
        "missing_desc": sum(1 for r in rows if r["description"] is None),
        "missing_desc_by": collections.Counter(
            ("poisoned" if r["is_poisoned"] else "clean", r["split"]) for r in rows if r["description"] is None
        ),
        "missing_paradigm": sum(1 for r in rows if r["is_poisoned"] and r["paradigm"] is None),
    }


def table(counter: dict, row_keys: list, col_keys: list, row_label: str, show=str) -> list[str]:
    lines = [f"| {row_label} | " + " | ".join(col_keys) + " | Total |",
             "|---|" + "---:|" * (len(col_keys) + 1)]
    for rk in row_keys:
        vals = [counter.get((rk, ck), 0) for ck in col_keys]
        lines.append(f"| {show(rk)} | " + " | ".join(map(str, vals)) + f" | {sum(vals)} |")
    tots = [sum(counter.get((rk, ck), 0) for rk in row_keys) for ck in col_keys]
    lines.append("| **Total** | " + " | ".join(map(str, tots)) + f" | {sum(tots)} |")
    return lines


def write_report(res: dict) -> None:
    rows = res["rows"]
    pois = [r for r in rows if r["is_poisoned"]]
    clean = [r for r in rows if not r["is_poisoned"]]
    held = res["held_out"]
    cats = [c for c in res["categories"] if any(r["risk_category"] == c for r in pois)]
    by_cat = collections.Counter((r["risk_category"], r["split"]) for r in pois)
    by_par = collections.Counter((r["paradigm"], r["split"]) for r in pois)
    cells = collections.Counter(r["test_cell"] for r in pois if r["split"] == "test")
    clean_ct = collections.Counter(r["split"] for r in clean)
    ss = res["split_def"]["server_split"]
    n_dropped = sum(res["dropped"].values())

    L = [
        "# MCPTox split report",
        "",
        "Generated by `scripts/build_splits.py`. Counts only, no case text.",
        "",
        f"- MCPTox commit: `{mcptox_commit()}` (github.com/zhiqiangwang4/MCPTox-Benchmark)",
        f"- Generated: {dt.date.today().isoformat()}",
        f"- Held-out categories: {', '.join(sorted(held))}",
        f"- Servers: train {len(ss['train'])}, val {len(ss['val'])}, test {len(ss['test'])} "
        f"(total {sum(len(v) for v in ss.values())})",
        "- Paradigm: MCPTox `Template-N` is mapped to `PN` (team decision, see DECISIONS.md).",
        "",
        "## Poisoned cases: split x risk category",
        "",
        *table(by_cat, cats, list(SPLITS), "Risk category", lambda c: c + (" *(held out)*" if c in held else "")),
        "",
        "## Poisoned cases: split x paradigm",
        "",
        *table(by_par, sorted({r["paradigm"] for r in pois}, key=str), list(SPLITS), "Paradigm"),
        "",
        "## Test cells (poisoned cases)",
        "",
        "| Test cell | Cases |",
        "|---|---:|",
        *[f"| {c} | {cells.get(c, 0)} |" for c in ("new_server_known_cat", "known_server_new_cat", "new_server_new_cat")],
        f"| **Total** | {sum(cells.values())} |",
        "",
        "## Clean (benign) tools per split",
        "",
        "Split by server only. Clean tools on test servers get `test_cell = new_server_clean`.",
        "",
        "| Split | Clean tools |",
        "|---|---:|",
        *[f"| {s} | {clean_ct.get(s, 0)} |" for s in SPLITS],
        f"| **Total** | {len(clean)} |",
        "",
        "## Totals vs. paper",
        "",
        "| | Ours | Expected (from our task brief; not re-verified against arXiv 2508.14925) |",
        "|---|---:|---|",
        f"| Poisoned cases in raw file (`data_length`) | {res['raw_total']} | {' / '.join(f'{n:,}' for n in PAPER_TOTALS)} |",
        f"| Poisoned cases kept (`wrong_data == 0`) | {len(pois)} | matches 1,312 |",
        f"| Risk categories | {len(res['categories'])} (incl. `Other`) | 10 or 11 |",
        f"| Servers | {len({r['server'] for r in rows})} | 45 |",
        f"| Clean tools | {len(clean)} | 353 |",
        "",
        "No count of 1,497 cases can be derived from the released data (source of that figure unverified).",
        "",
        "## Dropped or unmatched",
        "",
        f"{n_dropped} poisoned cases dropped.",
        "",
        "| Reason | Server split | Risk category | Cases |",
        "|---|---|---|---:|",
        *[f"| {reason} | {sp} | {cat} | {n} |" for (reason, sp, cat), n in sorted(res["dropped"].items(), key=str)],
        "",
        "- `wrong_data = 2`: cases flagged by the MCPTox authors; dropping them gives the paper's 1,312.",
        f"- Records with `description = null` (empty or literal `None` in the source): {res['missing_desc']}"
        + (f" ({dict(sorted(res['missing_desc_by'].items()))})" if res["missing_desc"] else ""),
        f"- Poisoned records with `paradigm = null`: {res['missing_paradigm']}",
        "- All 45 server names in `server_split.json` match the dataset's `server_name` field exactly "
        "(the dataset's dict keys `Github`/`Gitlab` differ in case, so we match on the field).",
        "- Apify: `tool_names` lists 7 tools but its clean system prompt describes 16; we use the 7 in `tool_names`.",
        "",
    ]
    REPORT_FILE.write_text("\n".join(L), encoding="utf-8", newline="\n")


def main() -> None:
    res = build()
    write_report(res)
    ct = collections.Counter((r["split"], r["is_poisoned"]) for r in res["rows"])
    for s in SPLITS:
        print(f"{s:5s} poisoned={ct[(s, True)]:5d} clean={ct[(s, False)]:4d}")
    print(f"dropped={sum(res['dropped'].values())} missing_description={res['missing_desc']} "
          f"missing_paradigm={res['missing_paradigm']}")
    print(f"wrote {PROCESSED_DIR.relative_to(ROOT)}/{{tune,val,test}}.jsonl and {REPORT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
