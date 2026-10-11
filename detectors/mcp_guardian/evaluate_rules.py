"""Score MCP Guardian, as published, on Team 12's official MCPTox split (tune and val only).

    uv run python -m detectors.mcp_guardian.evaluate_rules
    uv run python -m detectors.mcp_guardian.evaluate_rules --split tune --show-misses 10

Unit: one MCPTox case (poisoned) or one clean tool, as built by
``scripts/build_splits.py``. The test split is never loaded here.

The rules are the paper's WAF, written before MCPTox was opened and never tuned
on it, so tune and val are both unseen data for this detector. ``--show-misses``
is for error analysis in the report, not for changing rules.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict

from .team_split import DEV_SPLITS, Example, load_split
from .waf import WafScanner


def _scores(caught: list[bool], flagged_clean: int, n_clean: int) -> str:
    tp = sum(caught)
    precision = tp / (tp + flagged_clean) if tp + flagged_clean else 0.0
    recall = tp / len(caught) if caught else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return (
        f"recall {recall:.3f} ({tp}/{len(caught)})   precision {precision:.3f}   F1 {f1:.3f}   "
        f"FPR {flagged_clean / n_clean:.3f} ({flagged_clean}/{n_clean})"
    )


def report(scanner: WafScanner, split: str, examples: list[Example], misses: int) -> None:
    poisoned = [e for e in examples if e.poisoned]
    clean = [e for e in examples if not e.poisoned]
    rules = {id(e): set(scanner.scan(e.tool).rules) for e in examples}
    flagged_clean = sum(bool(rules[id(e)]) for e in clean)

    print(f"\n=== {split}: {len(poisoned)} poisoned cases, {len(clean)} clean tools ===")
    print(_scores([bool(rules[id(e)]) for e in poisoned], flagged_clean, len(clean)))

    for label, key in (("category", "category"), ("attack type", "paradigm")):
        groups: dict[str, list[Example]] = defaultdict(list)
        for e in poisoned:
            groups[getattr(e, key)].append(e)
        cells = [f"{g} {sum(bool(rules[id(e)]) for e in items)}/{len(items)}" for g, items in sorted(groups.items())]
        print(f"recall by {label}: " + "; ".join(cells))

    hits, servers, clean_hits = Counter(), defaultdict(set), Counter()
    for e in poisoned:
        for rule in rules[id(e)]:
            hits[rule] += 1
            servers[rule].add(e.server)
    for e in clean:
        clean_hits.update(rules[id(e)])
    fired = [r.name for r in scanner.rules if hits[r.name] or clean_hits[r.name]]
    print(
        "rules that fired (poisoned cases / servers / clean tools): "
        + ("; ".join(f"{r} {hits[r]}/{len(servers[r])}/{clean_hits[r]}" for r in fired) or "none")
    )

    for e in clean:
        if rules[id(e)]:
            print(f"false positive: {e.server}/{e.tool['name']} -> {sorted(rules[id(e)])}")
    for e in [e for e in poisoned if not rules[id(e)]][:misses]:
        print(f"miss [{e.paradigm} | {e.category} | {e.source}]: {e.tool['description'][:300]!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", action="append", choices=DEV_SPLITS, help="tune and/or val (default: both)")
    parser.add_argument("--show-misses", type=int, default=0, metavar="N", help="print up to N missed attacks")
    args = parser.parse_args()

    scanner = WafScanner()
    print(f"MCP Guardian WAF, {len(scanner.rules)} rules, fingerprint {scanner.fingerprint}")
    for split in args.split or list(DEV_SPLITS):
        report(scanner, split, load_split(split), args.show_misses)


if __name__ == "__main__":
    main()
