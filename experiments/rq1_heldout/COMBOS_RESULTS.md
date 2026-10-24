# RQ1 robustness check: 8 other held-out category combinations

Team 12, Experiment 1. The first RQ1 run ([RESULTS.md](RESULTS.md)) held out Credential Leakage, Instruction Tampering and Financial Loss. To check that its conclusions are not specific to those three categories, we repeated the **whole pipeline from scratch** on 8 other 3-category hold-outs. For each one we built the split, retrained all 20 fine-tuned models on that split's `tune` data, and scored all six detectors on its val, held-out and whole test split.

## Summary

- **The learned detectors' result holds for every combination.** With Stage I + II, every MCP-Guard and Base E5 variant keeps 99.2–100% held-out recall and 98.8–100 F1 in all 8 combinations, the same picture as the first run.
- **MCP Guardian's first-run score was category luck.** It caught 36.1% of the first run's held-out attacks, but only 0.6–11.3% (mean 6.0%) on the new combinations.
- **New finding: MCP-Guard's classifier is weak on Infrastructure Damage.** With the classifier alone (Stage II), MCP-Guard's encoder catches only about 75–79% of held-out Infrastructure Damage attacks, whether used as released (75.4%), fully fine-tuned (77.3%) or head-only fine-tuned (75.3%). Base E5 Full catches 97.5%. MCP-Guard's regex Stage I catches all of them, which is why the full pipeline still scores 100%.
- **Base E5 Full is the most consistent detector.** It has the highest classifier-alone recall (99.7 ± 0.3% across combinations, range 99.1–100) and the fewest false positives (0.2 ± 0.2%, range 0.0–0.3).
- The caveats of the first run still apply: MCPTox attacks share templates and length cues across categories (see Caveats below).

## 1. What we did

| | |
|---|---|
| Combinations | 8 of the 35 possible 3-of-7 combinations, drawn by a fixed rule before any results: the pool is the 7 categories not held out in the first run (`Other` excluded), seed 2026, redrawn until each category is held out 3–4 times ([combos.py](combos.py), [combos/combos.json](combos/combos.json)) |
| Times each category is held out | Code Injection 3, Data Tampering 4, Information Manipulation 4, Infrastructure Damage 3, Message Hijacking 3, Privacy Leakage 3, Service Disruption 4 |
| Splits | Same 30 / 6 / 9 server split as the first run; only the held-out categories change. Built with `scripts/build_splits.py`, unchanged. The first run's three categories are ordinary training categories here. Clean tools are the same in every combination: 240 tune, 49 val, 64 test. |
| Models | The same six detectors as the first run. The four fine-tuned variants were retrained per combination (5 seeds each), with the same hyperparameters, best epoch picked on that combination's val split. Frozen MCP-Guard and MCP Guardian are unchanged. |
| Scoring | Same code and metrics as the first run ([README.md](README.md)): MCP-Guard Stage I + II (paper mode, T_u = 0.45) and Stage II alone; held-out poisoned cases + 64 clean test tools; the whole test split; val. |
| Run | CARC, job array `13272593` (8 × A40, code at commit `9185380`), 2026-10-21, ~24 min per combination. 160 models trained (0 failures), 1,032 evaluation runs (0 errors). Checkpoints were deleted after scoring; training records and sample-level predictions were kept. |
| Not done yet | The same run on a laptop, pending a decision. |

Consistency check: Frozen MCP-Guard and MCP Guardian are not retrained. Their per-category numbers are identical in every combination that holds a category out, and Frozen's false-positive rate is 3.1% in every run.

## 2. Findings

1. **Category choice doesn't matter for the learned detectors in the full pipeline.** With Stage I + II, held-out recall stays between 99.2% (MCP-Guard Head-Only, c5) and 100% for every learned model in every combination, and whole-test recall stays at 99.4–100%. The first run's near-perfect numbers are typical, not a lucky split.
2. **Guardian depends entirely on which categories happen to match its 11 rules.** It catches 18.9% of Infrastructure Damage and 12.7% of Code Injection, but 0% of Message Hijacking and Service Disruption, and 1.1% of Information Manipulation. Its first-run 36.1% came from Credential Leakage matching its SSH-key and secrets rules.
3. **The classifier alone shows real differences between encoders.**
   - Whenever Infrastructure Damage is held out (c5, c6, c7), the MCP-Guard variants' classifier-alone combined recall drops to 91.5–94.1%, while Base E5 Full stays at 99.1–99.5%.
   - Fine-tuning MCP-Guard on the other categories barely helps this category (75.4% released → 77.3% fully fine-tuned). The gap sits in the encoder, not the head.
4. **Full fine-tuning beats head-only, again.** The head-only variants flag the most clean tools: Base E5 Head-Only 6.3 ± 1.5% across combinations, MCP-Guard Head-Only 4.6 ± 1.2%. The full fine-tunes flag 0.2% (E5) and 1.9% (MCP-Guard).
5. **Val can't tell the models apart.** Every learned model scores 100% val recall in every combination. Model choice can't be made on val recall here; only false-positive rate separates them.

## 3. Caveats

- **Same template and length cues as the first run.** Every MCPTox category is written with the same injection templates, and clean descriptions are much shorter than poisoned ones. Stage I alone still catches most attacks. High held-out recall therefore shows that the detectors recognize MCPTox's style, not that they understand new kinds of harm (Experiment 2 tests that).
- **The combinations overlap.** Each category appears in 3–4 of the 8 combinations, so the spread across combinations understates the true uncertainty. Read "mean ± std across combinations" as a description, not a confidence interval.
- **Held-out sizes differ** (221–587 cases), and so does the amount of training data (500–756 poisoned training cases).
- **The clean set is small (64) and identical in every combination.** FPR differences between combinations come only from retraining, and one false positive is 1.6 points.
- **The test split is reused.** Every combination scores rows from the same MCPTox test servers. These are robustness checks on one benchmark, not independent test sets.

## 4. Files

| What | Where |
|---|---|
| This overview | `experiments/rq1_heldout/COMBOS_RESULTS.md` |
| Full results per combination: split counts, training summary, every held-out and whole-test table, both configurations | [combos/results/c1.md](combos/results/c1.md) … [c8.md](combos/results/c8.md) |
| Cross-combination tables (also below) | [combos/results/tables.md](combos/results/tables.md) |
| Raw outputs: predictions, metrics, logs, training records (gitignored) | `results/rq1_combos/<combo>/` locally and on CARC |
| Regenerate these documents | `uv run python -m experiments.rq1_heldout.combos_report && uv run python -m experiments.rq1_heldout.combos_docs` |

# Tables

## Per-combination results (Stage I + II unless noted; held-out poisoned + 64 clean test tools)

### c1: Code Injection, Data Tampering, Message Hijacking (221 held-out cases) — [details](combos/results/c1.md)

| Model | Code Injection (n=63) | Data Tampering (n=117) | Message Hijacking (n=41) | **Combined** | F1 | FPR | Combined, Stage II alone | Whole-test recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 97.6 | **99.5** | 99.3 | 3.1 | 98.6 | 99.7 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 99.6 ± 0.5 | 2.8 ± 3.2 | 100.0 ± 0.0 | 99.9 ± 0.1 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 99.7 ± 0.8 | 98.5 ± 1.3 | **99.5 ± 0.6** | 99.1 ± 0.2 | 4.4 ± 2.6 | 99.0 ± 1.0 | 99.7 ± 0.3 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.1 | 0.3 ± 0.7 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| Base E5 Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 98.8 ± 0.7 | 8.1 ± 4.9 | 98.5 ± 1.1 | 100.0 ± 0.0 |
| MCP-Guardian | 12.7 | 7.7 | 0.0 | **7.7** | 14.3 | 0.0 | 7.7 | 7.5 |

### c2: Code Injection, Data Tampering, Privacy Leakage (453 held-out cases) — [details](combos/results/c2.md)

| Model | Code Injection (n=63) | Data Tampering (n=117) | Privacy Leakage (n=273) | **Combined** | F1 | FPR | Combined, Stage II alone | Whole-test recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 98.9 | **99.3** | 99.4 | 3.1 | 97.6 | 99.5 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 99.9 ± 0.2 | **99.9 ± 0.1** | 99.8 ± 0.1 | 1.6 ± 1.6 | 99.9 ± 0.1 | 99.9 ± 0.1 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 98.9 ± 0.0 | **99.3 ± 0.0** | 99.3 ± 0.2 | 5.6 ± 2.6 | 97.8 ± 0.5 | 99.5 ± 0.0 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 99.4 ± 0.7 | **99.6 ± 0.4** | 99.8 ± 0.2 | 0.0 ± 0.0 | 99.6 ± 0.4 | 99.7 ± 0.3 |
| Base E5 Head-Only | 99.0 ± 0.9 | 100.0 ± 0.0 | 99.7 ± 0.4 | **99.7 ± 0.3** | 99.5 ± 0.2 | 4.4 ± 4.9 | 98.9 ± 0.7 | 99.6 ± 0.3 |
| MCP-Guardian | 12.7 | 7.7 | 9.5 | **9.5** | 17.3 | 0.0 | 9.5 | 8.4 |

### c3: Code Injection, Privacy Leakage, Service Disruption (532 held-out cases) — [details](combos/results/c3.md)

| Model | Code Injection (n=63) | Privacy Leakage (n=273) | Service Disruption (n=196) | **Combined** | F1 | FPR | Combined, Stage II alone | Whole-test recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 98.9 | 100.0 | **99.4** | 99.5 | 3.1 | 97.2 | 99.5 |
| MCP-Guard Full | 100.0 ± 0.0 | 99.6 ± 0.5 | 100.0 ± 0.0 | **99.8 ± 0.3** | 99.8 ± 0.2 | 2.2 ± 2.1 | 98.6 ± 0.8 | 99.8 ± 0.2 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 98.9 ± 0.0 | 100.0 ± 0.0 | **99.4 ± 0.0** | 99.4 ± 0.2 | 5.0 ± 2.8 | 97.3 ± 0.4 | 99.5 ± 0.0 |
| Base E5 Full | 99.7 ± 0.7 | 99.6 ± 0.2 | 100.0 ± 0.0 | **99.7 ± 0.1** | 99.9 ± 0.1 | 0.0 ± 0.0 | 99.7 ± 0.1 | 99.8 ± 0.1 |
| Base E5 Head-Only | 99.0 ± 0.9 | 100.0 ± 0.0 | 100.0 ± 0.0 | **99.9 ± 0.1** | 99.5 ± 0.2 | 8.1 ± 3.0 | 99.1 ± 0.3 | 99.8 ± 0.1 |
| MCP-Guardian | 12.7 | 9.5 | 0.0 | **6.4** | 12.0 | 0.0 | 6.4 | 6.1 |

### c4: Data Tampering, Information Manipulation, Service Disruption (582 held-out cases) — [details](combos/results/c4.md)

| Model | Data Tampering (n=117) | Information Manipulation (n=269) | Service Disruption (n=196) | **Combined** | F1 | FPR | Combined, Stage II alone | Whole-test recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 99.3 | 100.0 | **99.7** | 99.7 | 3.1 | 97.8 | 99.7 |
| MCP-Guard Full | 100.0 ± 0.0 | 99.9 ± 0.2 | 100.0 ± 0.0 | **100.0 ± 0.1** | 99.8 ± 0.0 | 2.5 ± 0.9 | 99.7 ± 0.4 | 100.0 ± 0.1 |
| MCP-Guard Head-Only | 99.8 ± 0.4 | 99.3 ± 0.0 | 100.0 ± 0.0 | **99.6 ± 0.1** | 99.6 ± 0.1 | 4.1 ± 2.1 | 97.8 ± 0.3 | 99.7 ± 0.1 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.0 | 0.3 ± 0.7 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| Base E5 Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 99.7 ± 0.7 | **99.9 ± 0.2** | 99.6 ± 0.2 | 5.9 ± 2.6 | 98.7 ± 1.2 | 99.6 ± 0.4 |
| MCP-Guardian | 7.7 | 1.1 | 0.0 | **2.1** | 4.0 | 0.0 | 2.1 | 3.4 |

### c5: Data Tampering, Infrastructure Damage, Privacy Leakage (512 held-out cases) — [details](combos/results/c5.md)

| Model | Data Tampering (n=117) | Infrastructure Damage (n=122) | Privacy Leakage (n=273) | **Combined** | F1 | FPR | Combined, Stage II alone | Whole-test recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 98.9 | **99.4** | 99.5 | 3.1 | 92.0 | 99.5 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 99.5 ± 0.2 | **99.7 ± 0.1** | 99.8 ± 0.1 | 0.3 ± 0.7 | 94.1 ± 1.6 | 99.8 ± 0.1 |
| MCP-Guard Head-Only | 99.1 ± 0.6 | 100.0 ± 0.0 | 98.9 ± 0.0 | **99.2 ± 0.1** | 99.4 ± 0.0 | 2.8 ± 0.7 | 91.5 ± 0.5 | 99.4 ± 0.1 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 99.6 ± 0.0 | **99.8 ± 0.0** | 99.9 ± 0.0 | 0.0 ± 0.0 | 99.1 ± 0.5 | 99.8 ± 0.0 |
| Base E5 Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 99.5 ± 0.4 | **99.7 ± 0.2** | 99.4 ± 0.2 | 6.9 ± 4.2 | 97.8 ± 1.3 | 99.7 ± 0.3 |
| MCP-Guardian | 7.7 | 18.9 | 9.5 | **11.3** | 20.4 | 0.0 | 11.3 | 10.0 |

### c6: Information Manipulation, Infrastructure Damage, Message Hijacking (432 held-out cases) — [details](combos/results/c6.md)

| Model | Information Manipulation (n=269) | Infrastructure Damage (n=122) | Message Hijacking (n=41) | **Combined** | F1 | FPR | Combined, Stage II alone | Whole-test recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 99.3 | 100.0 | 97.6 | **99.3** | 99.4 | 3.1 | 91.7 | 99.5 |
| MCP-Guard Full | 99.7 ± 0.2 | 100.0 ± 0.0 | 100.0 ± 0.0 | **99.8 ± 0.1** | 99.9 ± 0.1 | 0.6 ± 1.4 | 93.6 ± 1.0 | 99.9 ± 0.1 |
| MCP-Guard Head-Only | 99.3 ± 0.0 | 100.0 ± 0.0 | 99.0 ± 1.3 | **99.4 ± 0.1** | 99.2 ± 0.1 | 6.6 ± 2.3 | 92.0 ± 0.5 | 99.6 ± 0.1 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.1 | 0.3 ± 0.7 | 99.5 ± 0.6 | 100.0 ± 0.1 |
| Base E5 Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 99.5 ± 0.3 | 6.6 ± 3.6 | 98.8 ± 1.7 | 99.9 ± 0.2 |
| MCP-Guardian | 1.1 | 18.9 | 0.0 | **6.0** | 11.4 | 0.0 | 6.0 | 6.6 |

### c7: Information Manipulation, Infrastructure Damage, Service Disruption (587 held-out cases) — [details](combos/results/c7.md)

| Model | Information Manipulation (n=269) | Infrastructure Damage (n=122) | Service Disruption (n=196) | **Combined** | F1 | FPR | Combined, Stage II alone | Whole-test recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 99.3 | 100.0 | 100.0 | **99.7** | 99.7 | 3.1 | 93.0 | 99.7 |
| MCP-Guard Full | 99.4 ± 0.5 | 100.0 ± 0.0 | 100.0 ± 0.0 | **99.7 ± 0.2** | 99.8 ± 0.1 | 1.9 ± 1.3 | 93.7 ± 0.9 | 99.8 ± 0.2 |
| MCP-Guard Head-Only | 99.3 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **99.7 ± 0.0** | 99.6 ± 0.1 | 3.4 ± 1.7 | 92.9 ± 0.3 | 99.7 ± 0.0 |
| Base E5 Full | 100.0 ± 0.0 | 99.8 ± 0.4 | 100.0 ± 0.0 | **100.0 ± 0.1** | 100.0 ± 0.0 | 0.3 ± 0.7 | 99.4 ± 0.5 | 100.0 ± 0.1 |
| Base E5 Head-Only | 99.9 ± 0.2 | 100.0 ± 0.0 | 99.3 ± 0.5 | **99.7 ± 0.2** | 99.6 ± 0.1 | 4.1 ± 2.4 | 96.5 ± 1.8 | 99.5 ± 0.3 |
| MCP-Guardian | 1.1 | 18.9 | 0.0 | **4.4** | 8.5 | 0.0 | 4.4 | 5.3 |

### c8: Information Manipulation, Message Hijacking, Service Disruption (506 held-out cases) — [details](combos/results/c8.md)

| Model | Information Manipulation (n=269) | Message Hijacking (n=41) | Service Disruption (n=196) | **Combined** | F1 | FPR | Combined, Stage II alone | Whole-test recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 99.3 | 97.6 | 100.0 | **99.4** | 99.5 | 3.1 | 97.6 | 99.5 |
| MCP-Guard Full | 99.7 ± 0.2 | 100.0 ± 0.0 | 100.0 ± 0.0 | **99.8 ± 0.1** | 99.7 ± 0.2 | 3.1 ± 1.9 | 99.3 ± 0.4 | 99.9 ± 0.1 |
| MCP-Guard Head-Only | 99.3 ± 0.0 | 98.5 ± 1.3 | 100.0 ± 0.0 | **99.5 ± 0.1** | 99.4 ± 0.1 | 5.3 ± 3.0 | 97.8 ± 0.4 | 99.6 ± 0.1 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.0 | 0.0 ± 0.0 | 100.0 ± 0.1 | 99.9 ± 0.1 |
| Base E5 Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 99.6 ± 0.3 | 6.6 ± 4.2 | 99.4 ± 0.6 | 99.7 ± 0.2 |
| MCP-Guardian | 1.1 | 0.0 | 0.0 | **0.6** | 1.2 | 0.0 | 0.6 | 2.3 |

Each combination retrains the 20 fine-tuned models on its own `tune` split and scores all six detectors. `orig` is the first RQ1 run. Per combination: mean over 5 seeds for fine-tuned models. Across combinations: mean ± std of the 8 new combinations (orig excluded), then min–max.

| Set | Held-out categories | Held-out cases |
|---|---|---:|
| orig | Credential Leakage, Instruction Tampering, Financial Loss | 227 |
| c1 | Code Injection, Data Tampering, Message Hijacking | 221 |
| c2 | Code Injection, Data Tampering, Privacy Leakage | 453 |
| c3 | Code Injection, Privacy Leakage, Service Disruption | 532 |
| c4 | Data Tampering, Information Manipulation, Service Disruption | 582 |
| c5 | Data Tampering, Infrastructure Damage, Privacy Leakage | 512 |
| c6 | Information Manipulation, Infrastructure Damage, Message Hijacking | 432 |
| c7 | Information Manipulation, Infrastructure Damage, Service Disruption | 587 |
| c8 | Information Manipulation, Message Hijacking, Service Disruption | 506 |

### Held-out combined accuracy (= recall) — Stage I + II

| Model | orig | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | Mean ± std (8 new) | Min–max (8 new) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 99.5 | 99.3 | 99.4 | 99.7 | 99.4 | 99.3 | 99.7 | 99.4 | 99.5 ± 0.1 | 99.3–99.7 |
| MCP-Guard Full | 100.0 | 100.0 | 99.9 | 99.8 | 100.0 | 99.7 | 99.8 | 99.7 | 99.8 | 99.9 ± 0.1 | 99.7–100.0 |
| MCP-Guard Head-Only | 100.0 | 99.5 | 99.3 | 99.4 | 99.6 | 99.2 | 99.4 | 99.7 | 99.5 | 99.5 ± 0.1 | 99.2–99.7 |
| Base E5 Full | 100.0 | 100.0 | 99.6 | 99.7 | 100.0 | 99.8 | 100.0 | 100.0 | 100.0 | 99.9 ± 0.1 | 99.6–100.0 |
| Base E5 Head-Only | 98.9 | 100.0 | 99.7 | 99.9 | 99.9 | 99.7 | 100.0 | 99.7 | 100.0 | 99.9 ± 0.1 | 99.7–100.0 |
| MCP-Guardian | 36.1 | 7.7 | 9.5 | 6.4 | 2.1 | 11.3 | 6.0 | 4.4 | 0.6 | 6.0 ± 3.6 | 0.6–11.3 |

### Held-out F1 (with 64 clean) — Stage I + II

| Model | orig | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | Mean ± std (8 new) | Min–max (8 new) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 99.6 | 99.3 | 99.4 | 99.5 | 99.7 | 99.5 | 99.4 | 99.7 | 99.5 | 99.5 ± 0.1 | 99.3–99.7 |
| MCP-Guard Full | 99.8 | 99.6 | 99.8 | 99.8 | 99.8 | 99.8 | 99.9 | 99.8 | 99.7 | 99.8 ± 0.1 | 99.6–99.9 |
| MCP-Guard Head-Only | 99.4 | 99.1 | 99.3 | 99.4 | 99.6 | 99.4 | 99.2 | 99.6 | 99.4 | 99.4 ± 0.2 | 99.1–99.6 |
| Base E5 Full | 100.0 | 100.0 | 99.8 | 99.9 | 100.0 | 99.9 | 100.0 | 100.0 | 100.0 | 99.9 ± 0.1 | 99.8–100.0 |
| Base E5 Head-Only | 98.6 | 98.8 | 99.5 | 99.5 | 99.6 | 99.4 | 99.5 | 99.6 | 99.6 | 99.5 ± 0.3 | 98.8–99.6 |
| MCP-Guardian | 53.1 | 14.3 | 17.3 | 12.0 | 4.0 | 20.4 | 11.4 | 8.5 | 1.2 | 11.1 ± 6.4 | 1.2–20.4 |

### FPR on 64 clean test tools — Stage I + II

| Model | orig | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | Mean ± std (8 new) | Min–max (8 new) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 3.1 | 3.1 | 3.1 | 3.1 | 3.1 | 3.1 | 3.1 | 3.1 | 3.1 | 3.1 ± 0.0 | 3.1–3.1 |
| MCP-Guard Full | 1.6 | 2.8 | 1.6 | 2.2 | 2.5 | 0.3 | 0.6 | 1.9 | 3.1 | 1.9 ± 1.0 | 0.3–3.1 |
| MCP-Guard Head-Only | 4.4 | 4.4 | 5.6 | 5.0 | 4.1 | 2.8 | 6.6 | 3.4 | 5.3 | 4.6 ± 1.2 | 2.8–6.6 |
| Base E5 Full | 0.3 | 0.3 | 0.0 | 0.0 | 0.3 | 0.0 | 0.3 | 0.3 | 0.0 | 0.2 ± 0.2 | 0.0–0.3 |
| Base E5 Head-Only | 6.2 | 8.1 | 4.4 | 8.1 | 5.9 | 6.9 | 6.6 | 4.1 | 6.6 | 6.3 ± 1.5 | 4.1–8.1 |
| MCP-Guardian | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 ± 0.0 | 0.0–0.0 |

### Held-out combined accuracy (= recall) — Stage II alone

| Model | orig | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | Mean ± std (8 new) | Min–max (8 new) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 98.6 | 97.6 | 97.2 | 97.8 | 92.0 | 91.7 | 93.0 | 97.6 | 95.7 ± 2.9 | 91.7–98.6 |
| MCP-Guard Full | 100.0 | 100.0 | 99.9 | 98.6 | 99.7 | 94.1 | 93.6 | 93.7 | 99.3 | 97.4 ± 3.0 | 93.6–100.0 |
| MCP-Guard Head-Only | 100.0 | 99.0 | 97.8 | 97.3 | 97.8 | 91.5 | 92.0 | 92.9 | 97.8 | 95.8 ± 3.1 | 91.5–99.0 |
| Base E5 Full | 99.9 | 100.0 | 99.6 | 99.7 | 100.0 | 99.1 | 99.5 | 99.4 | 100.0 | 99.7 ± 0.3 | 99.1–100.0 |
| Base E5 Head-Only | 95.5 | 98.5 | 98.9 | 99.1 | 98.7 | 97.8 | 98.8 | 96.5 | 99.4 | 98.4 ± 0.9 | 96.5–99.4 |
| MCP-Guardian | 36.1 | 7.7 | 9.5 | 6.4 | 2.1 | 11.3 | 6.0 | 4.4 | 0.6 | 6.0 ± 3.6 | 0.6–11.3 |

### Held-out F1 (with 64 clean) — Stage II alone

| Model | orig | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | Mean ± std (8 new) | Min–max (8 new) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 99.6 | 98.9 | 98.6 | 98.4 | 98.7 | 95.6 | 95.4 | 96.2 | 98.6 | 97.5 ± 1.5 | 95.4–98.9 |
| MCP-Guard Full | 99.8 | 99.6 | 99.8 | 99.2 | 99.7 | 96.9 | 96.6 | 96.6 | 99.5 | 98.5 ± 1.5 | 96.6–99.8 |
| MCP-Guard Head-Only | 99.4 | 98.9 | 98.5 | 98.3 | 98.7 | 95.4 | 95.3 | 96.1 | 98.5 | 97.5 ± 1.6 | 95.3–98.9 |
| Base E5 Full | 99.9 | 100.0 | 99.8 | 99.9 | 100.0 | 99.6 | 99.7 | 99.7 | 100.0 | 99.8 ± 0.2 | 99.6–100.0 |
| Base E5 Head-Only | 96.8 | 98.1 | 99.1 | 99.1 | 99.0 | 98.4 | 98.9 | 98.0 | 99.3 | 98.7 ± 0.5 | 98.0–99.3 |
| MCP-Guardian | 53.1 | 14.3 | 17.3 | 12.0 | 4.0 | 20.4 | 11.4 | 8.5 | 1.2 | 11.1 ± 6.4 | 1.2–20.4 |

### FPR on 64 clean test tools — Stage II alone

| Model | orig | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 | Mean ± std (8 new) | Min–max (8 new) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 3.1 | 3.1 | 3.1 | 3.1 | 3.1 | 3.1 | 3.1 | 3.1 | 3.1 | 3.1 ± 0.0 | 3.1–3.1 |
| MCP-Guard Full | 1.6 | 2.8 | 1.6 | 2.2 | 2.5 | 0.3 | 0.6 | 1.9 | 3.1 | 1.9 ± 1.0 | 0.3–3.1 |
| MCP-Guard Head-Only | 4.4 | 4.4 | 5.6 | 5.0 | 4.1 | 2.8 | 6.6 | 3.4 | 5.3 | 4.6 ± 1.2 | 2.8–6.6 |
| Base E5 Full | 0.3 | 0.3 | 0.0 | 0.0 | 0.3 | 0.0 | 0.3 | 0.3 | 0.0 | 0.2 ± 0.2 | 0.0–0.3 |
| Base E5 Head-Only | 6.2 | 8.1 | 4.4 | 8.1 | 5.9 | 6.9 | 6.6 | 4.1 | 6.6 | 6.3 ± 1.5 | 4.1–8.1 |
| MCP-Guardian | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 ± 0.0 | 0.0–0.0 |

### Whole test split recall — Stage I + II

| Model | orig | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 99.7 | 99.5 | 99.5 | 99.7 | 99.5 | 99.5 | 99.7 | 99.5 |
| MCP-Guard Full | 100.0 | 99.9 | 99.9 | 99.8 | 100.0 | 99.8 | 99.9 | 99.8 | 99.9 |
| MCP-Guard Head-Only | 100.0 | 99.7 | 99.5 | 99.5 | 99.7 | 99.4 | 99.6 | 99.7 | 99.6 |
| Base E5 Full | 100.0 | 100.0 | 99.7 | 99.8 | 100.0 | 99.8 | 100.0 | 100.0 | 99.9 |
| Base E5 Head-Only | 99.3 | 100.0 | 99.6 | 99.8 | 99.6 | 99.7 | 99.9 | 99.5 | 99.7 |
| MCP-Guardian | 23.0 | 7.5 | 8.4 | 6.1 | 3.4 | 10.0 | 6.6 | 5.3 | 2.3 |

### val recall (dev) — Stage I + II

| Model | orig | c1 | c2 | c3 | c4 | c5 | c6 | c7 | c8 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| MCP-Guard Full | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| MCP-Guard Head-Only | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| Base E5 Full | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| Base E5 Head-Only | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| MCP-Guardian | 13.5 | 6.6 | 4.1 | 9.0 | 13.5 | 11.0 | 16.5 | 19.8 | 16.9 |

### Errors

None.

## Recall per held-out category, averaged over the combinations that held it out — Stage I + II

Seed mean per combination, then mean over combinations (range across combinations in brackets).

| Held-out category (times held out) | Frozen MCP-Guard | MCP-Guard Full | MCP-Guard Head-Only | Base E5 Full | Base E5 Head-Only | MCP-Guardian |
|---|---:|---:|---:|---:|---:|---:|
| Code Injection (3) | 100.0 | 100.0 | 100.0 | 99.9 (99.7–100.0) | 99.4 (99.0–100.0) | 12.7 |
| Data Tampering (4) | 100.0 | 100.0 | 99.7 (99.1–100.0) | 100.0 | 100.0 | 7.7 |
| Information Manipulation (4) | 99.3 | 99.7 (99.4–99.9) | 99.3 | 100.0 | 100.0 (99.9–100.0) | 1.1 |
| Infrastructure Damage (3) | 100.0 | 100.0 | 100.0 | 99.9 (99.8–100.0) | 100.0 | 18.9 |
| Message Hijacking (3) | 97.6 | 100.0 | 98.7 (98.5–99.0) | 100.0 | 100.0 | 0.0 |
| Privacy Leakage (3) | 98.9 | 99.7 (99.5–99.9) | 98.9 | 99.5 (99.4–99.6) | 99.7 (99.5–100.0) | 9.5 |
| Service Disruption (4) | 100.0 | 100.0 | 100.0 | 100.0 | 99.7 (99.3–100.0) | 0.0 |

## Recall per held-out category, averaged over the combinations that held it out — Stage II alone

Seed mean per combination, then mean over combinations (range across combinations in brackets).

| Held-out category (times held out) | Frozen MCP-Guard | MCP-Guard Full | MCP-Guard Head-Only | Base E5 Full | Base E5 Head-Only | MCP-Guardian |
|---|---:|---:|---:|---:|---:|---:|
| Code Injection (3) | 100.0 | 100.0 | 100.0 | 99.9 (99.7–100.0) | 94.5 (94.0–95.6) | 12.7 |
| Data Tampering (4) | 98.3 | 100.0 | 98.5 (97.6–99.3) | 100.0 | 100.0 | 7.7 |
| Information Manipulation (4) | 98.1 | 99.3 (98.7–99.9) | 98.2 (98.1–98.2) | 100.0 (99.9–100.0) | 98.6 (97.7–99.7) | 1.1 |
| Infrastructure Damage (3) | 75.4 | 77.3 (75.6–79.2) | 75.3 (74.9–75.9) | 97.5 (97.0–98.4) | 93.3 (90.7–96.4) | 18.9 |
| Message Hijacking (3) | 97.6 | 99.8 (99.5–100.0) | 98.7 (98.5–99.0) | 100.0 | 99.3 (98.5–100.0) | 0.0 |
| Privacy Leakage (3) | 96.7 | 99.3 (99.0–99.9) | 96.6 (96.3–96.8) | 99.5 (99.4–99.6) | 99.5 (99.0–99.9) | 9.5 |
| Service Disruption (4) | 96.9 | 98.5 (97.7–99.3) | 97.0 (96.7–97.2) | 100.0 | 99.3 (98.6–99.8) | 0.0 |
