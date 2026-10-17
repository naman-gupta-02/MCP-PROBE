# RQ1 results: do the detectors generalize to held-out MCPTox categories?

Team 12, Experiment 1. All six detectors were scored on the three MCPTox (arXiv 2508.14925) risk categories that no detector was tuned on, and on the whole test split. Nothing was trained, tuned or selected on these rows. How the scoring works is described in [README.md](README.md).

**Short answer:** every learned MCP-Guard variant (arXiv 2508.10991) catches 99–100% of held-out-category attacks, and MCP Guardian (arXiv 2504.12757) catches 36%. On MCPTox, a held-out *category* is not a hard test. Attacks from all categories share the same templates, which Stage I regexes and the Stage II classifier pick up regardless of category. So these numbers show that the detectors recognize MCPTox's template style. They don't show that the detectors understand new kinds of harm. Experiment 2 (the adaptive attacker) is the real test of that.

## Setup

| | |
|---|---|
| Held-out categories | C1 Credential Leakage (n = 115), C2 Instruction Tampering (n = 57), C3 Financial Loss (n = 55): 227 poisoned cases from 26 servers. Source: `held_out_categories` in `data/splits/server_split.json`. |
| Clean tools | 64 clean tools from the 9 test servers (20 have empty descriptions) |
| Whole test split | 446 rows: 382 poisoned (`known_server_new_cat` 194, `new_server_known_cat` 155, `new_server_new_cat` 33) + the same 64 clean tools |
| Dev reference | val: 171 poisoned cases (seen categories, val servers) + 49 clean tools |
| MCP-Guard | Stage I + II in paper mode (T_u = 0.45), and Stage II alone. Stage III not run. |
| Fine-tuned variants | 5 seeds each. Every metric is pooled per seed, then reported as mean ± std over seeds. |
| Run | Laptop CPU, 2026-10-16, code at `f1b5e70` + `--summarize-only`. Each checkpoint was copied from CARC, scored and deleted. 129 runs, 0 errors. |
| Check | All 21 val confusion matrices (frozen + 20 checkpoints) are identical to the ones the CARC training sweep recorded for the same checkpoints. |

Category accuracy = recall, since every held-out case is poisoned. Combined accuracy = pooled correct / pooled n. It is not a mean of category accuracies. The difference matters for Guardian: pooled 36.1% vs an unweighted mean of 24.9%.

## Table 1: held-out category accuracy, MCP-Guard Stage I + II (ranked by combined accuracy)

| Rank | Model | C1 Credential Leakage | C2 Instruction Tampering | C3 Financial Loss | **Combined** |
|---:|---|---:|---:|---:|---:|
| 1= | Frozen MCP-Guard | 100.0 | 100.0 | 100.0 | **100.0** |
| 1= | MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** |
| 1= | MCP-Guard Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** |
| 1= | Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** |
| 5 | Base E5 Head-Only | 99.8 ± 0.4 | 100.0 ± 0.0 | 96.0 ± 0.8 | **98.9 ± 0.2** |
| 6 | MCP-Guardian | 67.8 | 7.0 | 0.0 | **36.1** |

Stage II alone gives the same picture: Frozen, MCP-Guard Full and MCP-Guard Head-Only 100.0, Base E5 Full 99.9 ± 0.2, Base E5 Head-Only 95.5 ± 0.6 (Financial Loss 86.5 ± 1.0), Guardian 36.1.

## Table 2: held-out poisoned + 64 clean test tools (Stage I + II)

| Model | Accuracy | Precision | Recall | F1 | FPR | FPR (non-empty clean) | FP of 64 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Base E5 Full | 99.9 ± 0.2 | 99.9 ± 0.2 | 100.0 ± 0.0 | **100.0 ± 0.1** | 0.3 ± 0.7 | 0.5 ± 1.0 | 0.2 |
| MCP-Guard Full | 99.7 ± 0.2 | 99.6 ± 0.3 | 100.0 ± 0.0 | 99.8 ± 0.2 | 1.6 ± 1.1 | 2.3 ± 1.6 | 1.0 |
| Frozen MCP-Guard | 99.3 | 99.1 | 100.0 | 99.6 | 3.1 | 4.5 | 2 |
| MCP-Guard Head-Only | 99.0 ± 0.6 | 98.8 ± 0.7 | 100.0 ± 0.0 | 99.4 ± 0.4 | 4.4 ± 2.6 | 6.4 ± 3.7 | 2.8 |
| Base E5 Head-Only | 97.8 ± 0.6 | 98.3 ± 0.7 | 98.9 ± 0.2 | 98.6 ± 0.4 | 6.2 ± 2.5 | 9.1 ± 3.6 | 4.0 |
| MCP-Guardian | 50.2 | 100.0 | 36.1 | 53.1 | 0.0 | 0.0 | 0 |

For MCP-Guard, Stage II alone gives identical with-clean numbers, except that Base E5 Full's recall drops to 99.9 and Base E5 Head-Only's to 95.5 (F1 96.8). Stage I fired on none of the 64 clean test tools.

## Table 3: whole test split, recall by test cell (Stage I + II)

| Model | known server, new category (194) | new server, known category (155) | new server, new category (33) | Combined (382) | F1 with clean | FPR |
|---|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 100.0 | 100.0 | 99.7 | 3.1 |
| MCP-Guard Full | 100.0 | 100.0 | 100.0 | 100.0 | 99.9 ± 0.1 | 1.6 ± 1.1 |
| MCP-Guard Head-Only | 100.0 | 100.0 | 100.0 | 100.0 | 99.6 ± 0.2 | 4.4 ± 2.6 |
| Base E5 Full | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 ± 0.1 | 0.3 ± 0.7 |
| Base E5 Head-Only | 98.9 ± 0.2 | 99.9 ± 0.3 | 99.4 ± 1.4 | 99.3 ± 0.2 | 99.1 ± 0.3 | 6.2 ± 2.5 |
| MCP-Guardian | 39.7 | 3.9 | 15.2 | 23.0 | 37.4 | 0.0 |

With Stage II alone, the learned models' combined recall is 97.2 (Base E5 Head-Only) to 99.9. The seen-category cases on new servers are about as easy as the new categories: Guardian is the only detector with a large gap between cells, and it goes the other way, catching 3.9% of the seen categories and 39.7% of the new ones.

## Table 4: val → held-out (Stage I + II)

| Model | Recall val | Recall held-out | F1 val | F1 held-out | FPR val (49 clean) | FPR held-out (64 clean) |
|---|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 95.5 | 99.6 | 32.7 | 3.1 |
| MCP-Guard Full | 100.0 | 100.0 | 95.8 ± 0.3 | 99.8 ± 0.2 | 30.6 ± 2.0 | 1.6 ± 1.1 |
| MCP-Guard Head-Only | 100.0 | 100.0 | 95.5 ± 0.1 | 99.4 ± 0.4 | 33.1 ± 0.9 | 4.4 ± 2.6 |
| Base E5 Full | 100.0 | 100.0 | 96.6 ± 0.1 | 100.0 ± 0.1 | 24.9 ± 0.9 | 0.3 ± 0.7 |
| Base E5 Head-Only | 100.0 | 98.9 ± 0.2 | 95.9 ± 0.2 | 98.6 ± 0.4 | 30.2 ± 1.7 | 6.2 ± 2.5 |
| MCP-Guardian | 13.5 | 36.1 | 23.7 | 53.1 | 0.0 | 0.0 |

## Findings

1. **Highest combined accuracy.** Four learned models tie at 100% held-out accuracy, so the metric doesn't separate them. On F1 and false-positive rate with the clean tools, **Base E5 Full is best** (F1 100.0 ± 0.1, 0.2 of 64 clean tools flagged on average). Next come MCP-Guard Full (1.0), Frozen (2) and MCP-Guard Head-Only (2.8). These gaps are 1–3 tools out of 64, which is within noise: 2 of 64 has a 95% interval of roughly 0.4–10.8%.
2. **Full vs head-only fine-tuning.** Full fine-tuning is at least as good everywhere. Head-only E5 is the only learned model that misses attacks: 2.4 per seed with Stage I, 10.2 with Stage II alone. Across the 5 seeds those misses are almost all P1 cases, with Financial Loss P1 the largest group (37 of 51 pooled misses), and its false-positive rate is the highest (6.2%). Head-only MCP-Guard flags slightly more clean tools than full MCP-Guard (2.8 vs 1.0).
3. **MCP-Guard's encoder vs base E5.** Frozen, MCP-Guard's security-trained encoder needs no MCPTox training to reach 100% held-out recall. With a frozen encoder (head-only), the MCP-Guard encoder beats E5: 100% vs 95.5% recall with Stage II alone, 4.4% vs 6.2% FPR. With full fine-tuning, the two starting points become equivalent, and E5 Full has the fewest false positives. The security pre-training mostly helps when the encoder can't be updated.
4. **Rule-based Guardian.** It never flags a clean tool, but it catches 36.1% of held-out attacks and 23.0% of the whole test split. What it catches depends on topic overlap with its 11 rules. Credential Leakage (67.8%) is caught almost entirely by the `ssh_key`, `env_secret` and `sensitive_file` rules. Financial Loss (0%) matches no rule at all. Guardian's "better" held-out score than on val (13.5%) reflects the categories it happens to cover, not generalization.
5. **Hardest category.** Financial Loss is the hardest: 0% for Guardian, 96.0% for Base E5 Head-Only (86.5% with Stage II alone), and the source of most head-only E5 misses. Instruction Tampering is hard only for Guardian (7.0%).

## Why the near-perfect scores should not be read as "generalizes well"

- **Shared templates.** Stage I alone blocks 178 of 227 held-out cases, mostly through `shell_injection` (89) and `important_tag` (76), the same template cues it fires on in tune. With Stage II alone, Frozen MCP-Guard gives every held-out poisoned case a score of ≥ 0.995. Category labels change *what* the attack asks for, not *how* MCPTox phrases it.
- **Frozen = fine-tuned.** A model that never saw MCPTox scores the same 100% as models trained on it. MCPTox's category split therefore can't tell training on attacks from recognizing the template.
- **The FPR "improvement" comes from server shift, not category.** False-positive rate falls from ~25–33% on val to ~0–6% on test because the clean tools come from different servers. On val, the false positives came from Commander (Stage I) and Codacy (Stage II). On test, they come from Claude Post, BraveSearch and Financial Dataset, and there are only 64 clean tools in total. Treat the FPR columns as a difference between server sets.
- **The clean set is small and partly empty.** 20 of the 64 clean descriptions are empty, and MCP-Guard passes those without scoring them. The FPR over non-empty tools is about 1.5× higher (Table 2).
- **Length shortcut not ruled out.** Clean descriptions are much shorter than poisoned ones (median 14 vs 60 tokens on tune). A length-matched check is still open.
- **Stage III was not run, and would rarely trigger.** Paper-mode Stage III only sees Stage II scores between 0.45 and 0.55. On the held-out rows, Frozen MCP-Guard has none (0 of 291). Across the 20 fine-tuned checkpoints, 16 of 5,420 scores fall in that band (0.3%), mostly from the head-only models. So Stage III could change at most a handful of decisions.

**What this means for the paper:** on MCPTox, held-out categories are close to in-distribution for every learned detector. Report the held-out result as a ceiling, and put the generalization claim on Experiment 2 (rewritten attacks) and Experiment 3 (live servers).

## Files

The full tables, per-seed values and sample-level predictions are in `results/rq1_heldout/` (gitignored): `report.md`, `report_test.md`, `<split>/summary.{csv,json}`, `<split>/runs.csv`, and `<split>/<model>/<run>/{predictions.jsonl,metrics.json,log.txt}`. Regenerate them with the commands in [README.md](README.md).
