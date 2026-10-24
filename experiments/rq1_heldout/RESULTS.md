# RQ1 results: do MCP tool-poisoning detectors generalize to unseen attack categories?

Team 12, Experiment 1 (generalization). This document records what we tested, how we tested it, every result we obtained and how to read them. It opens with a **full summary of all RQ1 work**: the first held-out run, its independent CARC rerun, and the robustness check on 8 other held-out combinations. Sections 1–11 then give the first run in full detail. The 8 combinations are detailed in [COMBOS_RESULTS.md](COMBOS_RESULTS.md) and [combos/results/](combos/results/). All tables are generated from the saved result files in `results/rq1_heldout/` and `results/rq1_combos/` (gitignored). How to rerun everything is in [README.md](README.md).

## Full summary of all RQ1 results

### The question

**Do MCP tool-poisoning detectors still catch attacks from risk categories they were never tuned on?** A detector reads each tool's description (from `tools/list`) and blocks it if it looks poisoned. We hold out whole MCPTox risk categories from tuning and training, then test on them.

### What was tested

| # | Detector | What it is | Trained on MCPTox by us? |
|---|---|---|---|
| 1 | Frozen MCP-Guard | MCP-Guard's released classifier (arXiv 2508.10991; `GenTelLab/MCP-Guard` @ `861a928`), trained by its authors on their own data | No |
| 2 | MCP-Guard Full | #1 with all weights fine-tuned on our `tune` split | Yes, 5 seeds |
| 3 | MCP-Guard Head-Only | #1 with its encoder frozen; only the classification head trained | Yes, 5 seeds |
| 4 | Base E5 Full | General-purpose `intfloat/multilingual-e5-base` encoder + new head, all weights trained | Yes, 5 seeds |
| 5 | Base E5 Head-Only | Same encoder frozen; only the new head trained | Yes, 5 seeds |
| 6 | MCP Guardian | Regex filter with the 11 rules from arXiv 2504.12757 (our reimplementation), never tuned | No |

- **Configurations:** MCP-Guard variants run with Stage I (MCP-Guard's 7 regex rules) + Stage II (the classifier), as deployed, and with Stage II alone, to compare encoders. Stage III (the LLM check) was not run.
- **Data:** MCPTox (arXiv 2508.14925): 1,312 poisoned cases + 353 clean (benign) tool descriptions from 45 real servers. Servers are split 30 / 6 / 9 into tune / val / test; the held-out categories appear only in test.
- **Held-out evaluation:** every case of the held-out categories, plus the 64 clean test tools.
- **Metrics:** category and combined accuracy (all held-out cases are poisoned, so this is recall; combined is pooled, not averaged); precision, recall, F1, FPR and confusion matrices with the clean tools; recall by attack type and test cell. Fine-tuned models are reported as mean ± std over 5 seeds.

### What was done

| Step | Details | Outcome |
|---|---|---|
| First run (held out: Credential Leakage, Instruction Tampering, Financial Loss) | The 20 fine-tuned models from the 2026-10-08 CARC training sweep, plus Frozen MCP-Guard and Guardian, scored on held-out (227 poisoned + 64 clean), the whole test split (382 + 64) and val (171 + 49) | Laptop, 2026-10-16: 129 runs, 0 errors |
| Independent CARC rerun | Same evaluation on an A40 GPU (jobs `13203627`, `12930667`, 2026-10-17/18) | All 41,151 predictions identical to the laptop run |
| Robustness check: 8 other combinations | 8 of the 35 possible 3-of-7 combinations (seeded, balanced draw, excluding the first run's categories); **all 20 models retrained per combination**; same scoring | CARC array `13272593`, 2026-10-21: 160 models trained, 1,032 runs, 0 failures |
| Untrained detectors on all of MCPTox | Frozen MCP-Guard and Guardian on all 1,665 MCPTox rows (never trained on MCPTox, so all of it is unseen for them) | Laptop, 2026-10-24 |
| Cross-dataset check | Base E5 Full and MCP-Guard Full (5 seeds each, original-run checkpoints from CARC) and Frozen MCP-Guard on MCP-Guard's released dev set (1,053 samples; the full MCP-AttackBench is not released) | Laptop, 2026-10-24; Frozen reproduces the paper's Table 4a exactly |

Before trusting any numbers, we checked that:
- Frozen MCP-Guard and Guardian reproduce their earlier val results exactly.
- All 21 val confusion matrices match the training sweep.
- The split builder reproduces the team's data byte for byte.
- No held-out examples were read.

### Result 1: the first run

Held-out poisoned + 64 clean test tools, Stage I + II (Stage II-alone recall in the last column):

| Detector | Credential Leakage (115) | Instruction Tampering (57) | Financial Loss (55) | **Combined (227)** | Precision | F1 | FPR | Combined, Stage II alone |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 100.0 | **100.0** | 99.1 | 99.6 | 3.1 | 100.0 |
| MCP-Guard Full | 100.0 | 100.0 | 100.0 | **100.0** | 99.6 | 99.8 | 1.6 | 100.0 |
| MCP-Guard Head-Only | 100.0 | 100.0 | 100.0 | **100.0** | 98.8 | 99.4 | 4.4 | 100.0 |
| Base E5 Full | 100.0 | 100.0 | 100.0 | **100.0** | 99.9 | 100.0 | 0.3 | 99.9 |
| Base E5 Head-Only | 99.8 | 100.0 | 96.0 | **98.9** | 98.3 | 98.6 | 6.2 | 95.5 |
| MCP Guardian | 67.8 | 7.0 | 0.0 | **36.1** | 100.0 | 53.1 | 0.0 | – |

On the whole test split (446 rows), the learned models reach 99.3–100% recall and F1 99.1–100; Guardian reaches 23.0% recall.

### Result 2: across 8 other held-out combinations

Mean ± std across the 8 combinations [min–max]; each combination's value is the mean over 5 seeds:

| Detector | Combined recall, Stage I + II | F1, Stage I + II | FPR (64 clean) | Combined recall, Stage II alone |
|---|---:|---:|---:|---:|
| Frozen MCP-Guard | 99.5 ± 0.1 [99.3–99.7] | 99.5 ± 0.1 | 3.1 ± 0.0 | 95.7 ± 2.9 [91.7–98.6] |
| MCP-Guard Full | 99.9 ± 0.1 [99.7–100.0] | 99.8 ± 0.1 | 1.9 ± 1.0 | 97.4 ± 3.0 [93.6–100.0] |
| MCP-Guard Head-Only | 99.5 ± 0.1 [99.2–99.7] | 99.4 ± 0.2 | 4.6 ± 1.2 | 95.8 ± 3.1 [91.5–99.0] |
| **Base E5 Full** | 99.9 ± 0.1 [99.6–100.0] | **99.9 ± 0.1** | **0.2 ± 0.2** | **99.7 ± 0.3 [99.1–100.0]** |
| Base E5 Head-Only | 99.9 ± 0.1 [99.7–100.0] | 99.5 ± 0.3 | 6.3 ± 1.5 | 98.4 ± 0.9 [96.5–99.4] |
| MCP Guardian | 6.0 ± 3.6 [0.6–11.3] | 11.1 ± 6.4 | 0.0 | – |

Recall with Stage II alone, per category, averaged over the combinations that held that category out:

| Held-out category | Frozen MCP-Guard | MCP-Guard Full | MCP-Guard Head-Only | Base E5 Full | Base E5 Head-Only | Guardian |
|---|---:|---:|---:|---:|---:|---:|
| Code Injection | 100.0 | 100.0 | 100.0 | 99.9 | 94.5 | 12.7 |
| Data Tampering | 98.3 | 100.0 | 98.5 | 100.0 | 100.0 | 7.7 |
| Information Manipulation | 98.1 | 99.3 | 98.2 | 100.0 | 98.6 | 1.1 |
| **Infrastructure Damage** | **75.4** | **77.3** | **75.3** | **97.5** | 93.3 | 18.9 |
| Message Hijacking | 97.6 | 99.8 | 98.7 | 100.0 | 99.3 | 0.0 |
| Privacy Leakage | 96.7 | 99.3 | 96.6 | 99.5 | 99.5 | 9.5 |
| Service Disruption | 96.9 | 98.5 | 97.0 | 100.0 | 99.3 | 0.0 |

### Result 3: held-out recall for all 10 categories

Each category's recall **in the split(s) where it was held out**: the first run for Credential Leakage, Instruction Tampering and Financial Loss, and the 3–4 combinations for the other seven (seed mean, then mean over splits). The full table with ranges is in [tables/TABLES.md](tables/TABLES.md), with CSVs alongside.

| Held-out category (cases) | Frozen MCP-Guard | MCP-Guard Full | MCP-Guard Head-Only | Base E5 Full | Base E5 Head-Only | MCP Guardian |
|---|---:|---:|---:|---:|---:|---:|
| Code Injection (63) | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 99.9 / 99.9 | 99.4 / 94.5 | 12.7 |
| Credential Leakage (115) | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 99.8 / 97.6 | 67.8 |
| Data Tampering (117) | 100.0 / 98.3 | 100.0 / 100.0 | 99.7 / 98.5 | 100.0 / 100.0 | 100.0 / 100.0 | 7.7 |
| Financial Loss (55) | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 99.6 | 96.0 / 86.5 | 0.0 |
| Information Manipulation (269) | 99.3 / 98.1 | 99.7 / 99.3 | 99.3 / 98.2 | 100.0 / 100.0 | 100.0 / 98.6 | 1.1 |
| Infrastructure Damage (122) | 100.0 / **75.4** | 100.0 / **77.3** | 100.0 / **75.3** | 99.9 / 97.5 | 100.0 / 93.3 | 18.9 |
| Instruction Tampering (57) | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 100.0 / 100.0 | 7.0 |
| Message Hijacking (41) | 97.6 / 97.6 | 100.0 / 99.8 | 98.7 / 98.7 | 100.0 / 100.0 | 100.0 / 99.3 | 0.0 |
| Privacy Leakage (273) | 98.9 / 96.7 | 99.7 / 99.3 | 98.9 / 96.6 | 99.5 / 99.5 | 99.7 / 99.5 | 9.5 |
| Service Disruption (196) | 100.0 / 96.9 | 100.0 / 98.5 | 100.0 / 97.0 | 100.0 / 100.0 | 99.7 / 99.3 | 0.0 |
| **Average over 10 categories** | **99.6 / 96.3** | **99.9 / 97.4** | **99.7 / 96.4** | **99.9 / 99.7** | **99.5 / 96.9** | **12.5** |
| Lowest category | 97.6 / 75.4 | 99.7 / 77.3 | 98.7 / 75.3 | 99.5 / 97.5 | 96.0 / 86.5 | 0.0 |

Each cell is *Stage I + II / Stage II alone*. Guardian is rules only.

**Untrained detectors on all of MCPTox.** These models were never trained on MCPTox, so all 1,312 attacks and 353 clean tools are unseen for them.
- **Frozen MCP-Guard:** recall 99.5% (Stage I + II) and 96.0% (Stage II alone), but it **wrongly flags 16.1% of clean tools** (57 of 353), mostly from the AdFin, Commander and OP.GG servers.
- **MCP Guardian:** recall 11.5%, flagging 1 of 353 clean tools.

Per-category numbers for both are in [tables/TABLES.md](tables/TABLES.md).

### Result 4: cross-dataset, on MCP-Guard's released dev set

The test set is GenTelLab's `test_data/dev.csv`: 1,053 short texts, 432 of them malicious. It is the data behind MCP-Guard's paper Table 4a. The full 70k MCP-AttackBench has not been released. The fine-tuned models are our MCPTox-trained checkpoints (5 seeds); P ≥ 0.5, as MCP-Guard uses.

| Model | Accuracy | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|---:|
| Frozen MCP-Guard (its home data) | 96.0 | 96.7 | 93.5 | 95.1 | 2.3 |
| MCP-Guard Full (fine-tuned on MCPTox) | 95.7 ± 0.7 | 98.6 ± 0.1 | 90.9 ± 1.7 | 94.6 ± 0.9 | 0.9 |
| **Base E5 Full** (fine-tuned on MCPTox) | 69.6 ± 2.0 | 98.7 ± 1.0 | **26.2 ± 5.1** | **41.2 ± 6.2** | 0.3 |

These are Stage II alone. With Stage I + II: Frozen 95.0 F1, MCP-Guard Full 94.5, Base E5 Full 62.3 (recall 45.6). The two thresholds differ by at most 0.6 points.

- **Fine-tuning on MCPTox didn't make MCP-Guard forget its own data.** F1 went from 95.1 to 94.6: about 11 more attacks missed, about 9 fewer false alarms.
- **Base E5 Full, near-perfect on MCPTox, misses about three-quarters of these attacks.** The ones it misses are short and varied (harmful requests, shell snippets, social engineering), and almost none use MCPTox's template wording. This is the clearest evidence that its MCPTox score reflects MCPTox's style.
- **Caveat:** this is MCP-Guard's in-distribution data, so it favors MCP-Guard. A neutral third dataset would be the fairest comparison.

### Answers to the research questions

1. **Which detector generalizes best?** **On MCPTox: Base E5 Full. Across datasets: MCP-Guard Full** (see Result 4). With Stage I + II, its held-out recall is within 0.3 points of the best detector in every one of the 9 splits. It has the highest classifier-alone recall (99.7 ± 0.3% across the new combinations, never below 99.1%) and the fewest false positives (0.0–0.3% everywhere). Its lead over the next-best models is small, a few clean tools out of 64. But on MCP-Guard's dev set it falls to 41.2 F1 (26% recall), while MCP-Guard Full keeps 94.6 F1. Base E5 Full's lead is specific to MCPTox. **MCP-Guard Full is the more robust detector overall**: within 0.2 F1 of E5 on MCPTox, and far better on other data.
2. **Full or head-only fine-tuning?** **Full**, consistently. The head-only models flag the most clean tools (Base E5 Head-Only 6.3%, MCP-Guard Head-Only 4.6%, vs 0.2% and 1.9% for the full fine-tunes). Head-only E5 is also the only learned model that missed held-out attacks with Stage I + II in the first run (Financial Loss).
3. **MCP-Guard's security-trained encoder or the general E5 encoder?** **On MCPTox, E5 (once fine-tuned). Outside MCPTox, MCP-Guard's, by far** (dev-set F1 94.6 vs 41.2 after the same MCPTox fine-tuning).
   - The first run suggested that MCP-Guard's encoder is better when frozen (head-only, classifier alone: 100% vs 95.5%). **That doesn't hold across the other combinations**: E5 Head-Only averages 98.4% vs 95.8%.
   - MCP-Guard's encoder has a blind spot. It catches only about 75–77% of held-out Infrastructure Damage attacks with the classifier alone, whether released, head-only or fully fine-tuned. Base E5 Full catches 97.5%.
   - MCP-Guard's advantage is that it needs no training at all: as released it already reaches 99.3–100% with its regex stage. Its security pre-training also survives MCPTox fine-tuning and keeps it working on other attack data, which E5 lacks.
4. **Rule-based Guardian vs learned classifiers?** Guardian never flags a clean tool (precision 100%, FPR 0%), but it catches few attacks. Its recall depends entirely on whether a category's wording overlaps with its 11 rules: 36.1% on the first run's categories (thanks to Credential Leakage's SSH-key and secrets wording), and 0.6–11.3% (mean 6.0%) on the other combinations. It catches 0% of Financial Loss, Message Hijacking and Service Disruption.
5. **Which categories are hardest?**
   - For the regex detector: Financial Loss, Message Hijacking and Service Disruption (0%).
   - For MCP-Guard's classifier: Infrastructure Damage (~75%).
   - For head-only E5: Financial Loss (first run, 96.0% with Stage I + II) and Code Injection (94.5% classifier alone).
   - With Stage I + II, the lowest category score for any learned model is 96.0% (head-only E5, Financial Loss, first run). In the 8 new combinations, none falls below 97.6%.

### How to interpret this: why near-perfect scores don't prove generalization

- **Not overfitting.** Scores on training data, val, held-out and the whole test split are all about the same (99–100%). Overfitting would show a gap.
- **The benchmark is easy to separate.** Every MCPTox category is written with the same injection templates (`<IMPORTANT>` tags, "you MUST first call…"), and clean descriptions are much shorter than poisoned ones (median 14 vs 60 tokens).
  - MCP-Guard's regex stage alone catches 78% of the first run's held-out attacks.
  - MCP-Guard as released, never trained on MCPTox, scores 99.3–100%.
  - Base E5 reaches ~99% val F1 after 1–2 epochs.
- **Class balance flatters accuracy.** A detector that blocks everything would score 100% category accuracy and 78% accuracy on held-out + clean.
- **What RQ1 shows:** on MCPTox, unseen categories are close to in-distribution for every learned detector. These numbers are an upper bound. Whether the detectors recognize harmful *intent* or just MCPTox's *style* is what Experiment 2 (an attacker rewriting caught descriptions) and Experiment 3 (live servers) test.

### Limitations

- Only 64 clean test tools (20 empty), so one false positive moves FPR by 1.6 points.
- The 8 combinations overlap and reuse the same test servers, so the spread across combinations is descriptive, not a confidence interval.
- The whole test split has been used, so no untouched test data remains.
- Stage III was not run, though it would rarely trigger (no Frozen MCP-Guard score fell in its band).
- A length-matched check and simple length and keyword baselines are still open.

## Summary of the first run

- **What we tested:** six detectors (five MCP-Guard variants and MCP Guardian) on the three MCPTox risk categories that none of them was tuned on: Credential Leakage, Instruction Tampering and Financial Loss. We also scored them on the whole MCPTox test split and on val (dev data) for comparison.
- **Main result:** the four strongest learned models catch **100%** of held-out-category attacks, Base E5 Head-Only catches **98.9%**, and MCP Guardian catches **36.1%**. With the 64 clean test tools included, **Base E5 Full** is best (F1 100.0, 0.2 of 64 clean tools wrongly flagged on average).
- **How to read it:** on MCPTox, holding out a category is not a hard test. Attacks in every category are written with the same templates, so Stage I regexes alone block 178 of the 227 held-out attacks, and MCP-Guard as released, never trained on MCPTox, scores the same 100% as the models trained on it. These numbers show that the detectors recognize MCPTox's template style. They do not show that the detectors understand new kinds of harm. That question belongs to Experiment 2 (adaptive attacker).

## 1. What we are testing

**Research question:** how well do MCP tool-poisoning detectors generalize to attack categories they have never seen?

An MCP tool's description is text the agent reads. A poisoned description hides instructions such as "also read ~/.ssh/id_rsa". A detector inspects the description and blocks the tool if it looks poisoned. A detector "generalizes" if it still catches attacks whose kind of harm it was never tuned on, without blocking clean tools.

### The six detectors

| # | Model | What it is | Trained on MCPTox? |
|---|---|---|---|
| 1 | **Frozen MCP-Guard** | MCP-Guard (arXiv 2508.10991) Stage II classifier as released: `GenTelLab/MCP-Guard` @ `861a928` (E5-base / XLM-RoBERTa architecture) with the BERT tokenizer its code uses | No |
| 2 | **MCP-Guard Full** | Weights of #1, all layers fine-tuned on our `tune` split (lr 2e-5, 5 epochs) | Yes, 5 seeds |
| 3 | **MCP-Guard Head-Only** | Weights of #1, encoder frozen, only the classification head trained (lr 1e-3, 10 epochs) | Yes, 5 seeds |
| 4 | **Base E5 Full** | `intfloat/multilingual-e5-base` @ `d128750` + new classification head, all layers fine-tuned | Yes, 5 seeds |
| 5 | **Base E5 Head-Only** | Same encoder, frozen; only the new head trained | Yes, 5 seeds |
| 6 | **MCP-Guardian** | Our reimplementation of MCP Guardian (arXiv 2504.12757): a regex filter with the paper's 11 rules (fingerprint `9decc37e4f86`), never tuned on MCPTox | No |

The fine-tuned models were trained on our `tune` split only: 759 poisoned cases (the seven non-held-out categories, plus 4 labelled "Other") and 223 non-empty clean tools. Training used class-weighted cross-entropy, AdamW, batch size 16 and max length 128, with the best epoch picked by val F1. Training ran on a CARC A40 (job `12848251`, 2026-10-08). Nothing was trained, tuned or selected in this experiment.

### Configurations

- **MCP-Guard Stage I + II** (main result): Stage I is MCP-Guard's 7 regex detectors. A hit blocks the tool. Otherwise Stage II blocks it if P(poisoned) > 0.45 (paper mode, `configs/mcp_guard.yaml`). Stage I is identical in all five MCP-Guard variants.
- **MCP-Guard Stage II alone**: only the classifier, same 0.45 threshold. This isolates the differences between encoders.
- **Stage III** (the LLM check) was **not run**. In paper mode it only sees Stage II scores between 0.45 and 0.55, which almost never occur here (Section 5.8).
- **Inputs:** MCP-Guard reads the tool description. Guardian reads the tool name + description, as in its own evaluator (`detectors/mcp_guardian/evaluate_rules.py`). Our records have no parameter schema.

## 2. Data

MCPTox (arXiv 2508.14925) at commit `f85189f`, split by `scripts/build_splits.py` using `data/splits/server_split.json`. The three held-out risk categories never appear in `tune` or `val`.

| Row set | Poisoned | Clean | Total | Used for |
|---|---:|---:|---:|---|
| **Held-out categories** | 227 (Credential Leakage 115, Instruction Tampering 57, Financial Loss 55; from 26 servers) | 64 (from the 9 test servers; 20 have empty descriptions) | **291** | Main RQ1 result |
| **Whole test split** | 382 (the 227 above + 155 seen-category cases on the 9 test servers) | the same 64 | **446** | Extra view by test cell |
| **val** (dev reference) | 171 (seen categories, 6 val servers) | 49 | 220 | Dev-side comparison |

The test split is divided into three test cells:

| Test cell | Poisoned cases | What it measures |
|---|---:|---|
| `known_server_new_cat` | 194 | New category, server seen in training |
| `new_server_known_cat` | 155 | Seen category, new server |
| `new_server_new_cat` | 33 | Both new |

**By attack type:**
- Held-out: P1 43, P2 96, P3 88.
- Whole test: P1 56, P2 147, P3 179.
- P1: the user asks for the tool directly. P2: a fake "background" tool triggers on related actions. P3: an unrelated tool rewrites another tool's parameters.

**Leakage control:**
- The test split loads only with `FINAL_EVAL=1`.
- The held-out run drops the 155 seen-category cases right after loading.
- Prediction files store case IDs, labels and verdicts only, never description text.
- All six models are scored on exactly the same rows.

## 3. What we did

1. **Code** (`experiments/rq1_heldout/`). `evaluate.py` reuses the existing `MCPGuard` pipeline, the fine-tuned checkpoint loader, `binary_metrics` and Guardian's `WafScanner`. `report.py` builds comparison tables, and `carc/*.slurm` holds the CARC jobs. Unit tests check that combined accuracy is pooled, not averaged.
2. **Checks before the real run, on val:**
   - Frozen MCP-Guard reproduced the earlier val report exactly (acc 92.7, F1 95.5, FPR 32.7).
   - Guardian matched its own evaluator (23 of 171 caught, 0 of 49 clean flagged).
   - A re-saved copy of the MCP-Guard weights, loaded through the fine-tuned loader, gave predictions identical to Frozen (0 differences).
   - A missing checkpoint is recorded as an error with no numbers filled in.
3. **CARC attempt.**
   - Job `12930071` (2026-10-12) hit its 1-hour limit with no runs finished. Some cached model files on CARC's `/scratch1` storage hung on any access, a storage fault rather than our code.
   - The whole-test job `12930667` was put on hold.
   - On 2026-10-16 the storage was readable again. We added a 2-minute startup check to the job script and resubmitted as `13203627`, with `12930667` chained after it.
4. **Local run (2026-10-16), which produced every number below.**
   - Each of the 20 fine-tuned checkpoints was copied from CARC to a laptop (~40 s per 1.1 GB), scored on val, held-out and the whole test split (both configurations), then deleted.
   - Frozen MCP-Guard and Guardian need no download.
   - 129 runs in total (43 per row set), 0 errors, about 32 minutes, on CPU.
5. **Cross-check.** All 21 val confusion matrices (Frozen + 20 checkpoints) are identical to the ones the CARC training sweep recorded on GPU for the same checkpoints.
6. **Independent CARC rerun.** Both CARC jobs later completed on an A40 GPU at commit `900773f`:
   - `13203627` (val + held-out) ran on 2026-10-17 in 5.5 min.
   - `12930667` (whole test) ran on 2026-10-18 in 3.2 min.
   - Together they cover the same 129 runs, with 0 errors.
   - All 41,151 predictions are identical to the laptop run, Stage II scores differ by at most 2.2e-5, and both generated reports are byte-identical.

   Every number below is therefore reproduced on CARC.

## 4. Metrics

| Metric | Definition |
|---|---|
| **Category accuracy** | correct / n within one risk category. Every case in a category is poisoned, so this equals **recall**: a detector that blocks everything would score 100%. |
| **Combined accuracy** | (correct in C1 + C2 + C3) / (n in C1 + C2 + C3): pooled over all held-out cases, not a mean of category accuracies. The unweighted mean is shown next to it only for comparison, and the code checks the pooled value. |
| **Precision / Recall / F1 / Accuracy** | Over poisoned cases **plus the clean tools** of the same row set (positive = poisoned). Precision is undefined inside a single category, because a category has no clean tools. |
| **FPR** | Clean tools wrongly blocked / all clean tools. Also given over non-empty clean tools only, because MCP-Guard passes empty descriptions without scoring them. |
| **Test-cell / attack-type recall** | Pooled recall within that group, poisoned cases only. |
| **Seeds** | Each fine-tuned seed is scored on its own. Tables show mean ± sample std over the 5 seeds, so confusion-matrix counts can be fractions. Frozen and Guardian have a single run. |

With 64 clean tools, one false positive moves the FPR by 1.6 points. As an example of the uncertainty, 2 of 64 has a 95% interval of about 0.4–10.8%.

## 5. Results on the held-out categories (main result)

### 5.1 Category accuracy and combined accuracy

**Stage I + II**

| Model | Credential Leakage * (n=115) | Instruction Tampering * (n=57) | Financial Loss * (n=55) | **Combined (pooled)** | Unweighted mean |
|---|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 100.0 | **100.0** | 100.0 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.0 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.0 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.0 |
| Base E5 Head-Only | 99.8 ± 0.4 | 100.0 ± 0.0 | 96.0 ± 0.8 | **98.9 ± 0.2** | 98.6 ± 0.3 |
| MCP-Guardian | 67.8 | 7.0 | 0.0 | **36.1** | 24.9 |

**Stage II alone**

| Model | Credential Leakage * (n=115) | Instruction Tampering * (n=57) | Financial Loss * (n=55) | **Combined (pooled)** | Unweighted mean |
|---|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 100.0 | **100.0** | 100.0 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.0 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.0 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 99.6 ± 0.8 | **99.9 ± 0.2** | 99.9 ± 0.3 |
| Base E5 Head-Only | 97.6 ± 0.7 | 100.0 ± 0.0 | 86.5 ± 1.0 | **95.5 ± 0.6** | 94.7 ± 0.5 |
| MCP-Guardian | 67.8 | 7.0 | 0.0 | **36.1** | 24.9 |

Correct predictions out of the total (Stage I + II; seed mean for fine-tuned):

| Model | Credential Leakage correct / 115 | Instruction Tampering correct / 57 | Financial Loss correct / 55 | Combined correct / 227 |
|---|---:|---:|---:|---:|
| Frozen MCP-Guard | 115 | 57 | 55 | 227 |
| MCP-Guard Full | 115.0 | 57.0 | 55.0 | 227.0 |
| MCP-Guard Head-Only | 115.0 | 57.0 | 55.0 | 227.0 |
| Base E5 Full | 115.0 | 57.0 | 55.0 | 227.0 |
| Base E5 Head-Only | 114.8 | 57.0 | 52.8 | 224.6 |
| MCP-Guardian | 78 | 4 | 0 | 82 |

Ranking by combined accuracy (Stage I + II):
1. Frozen MCP-Guard, MCP-Guard Full, MCP-Guard Head-Only and Base E5 Full tie at 100.0.
2. Base E5 Head-Only, 98.9.
3. MCP-Guardian, 36.1.

Stage II alone gives the same order, except that Base E5 Full drops to 99.9 and Base E5 Head-Only to 95.5. For Guardian, the pooled value (36.1) and the unweighted mean (24.9) differ a lot, because its catches come almost entirely from the largest category.

### 5.2 Held-out poisoned + 64 clean test tools (precision, recall, F1, confusion matrix)

**Stage I + II**

| Model | Accuracy | Precision | Recall | F1 | FPR (all clean) | FPR (non-empty clean) | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 99.3 | 99.1 | 100.0 | 99.6 | 3.1 | 4.5 | 227 | 2 | 0 | 62 |
| MCP-Guard Full | 99.7 ± 0.2 | 99.6 ± 0.3 | 100.0 ± 0.0 | 99.8 ± 0.2 | 1.6 ± 1.1 | 2.3 ± 1.6 | 227.0 | 1.0 | 0.0 | 63.0 |
| MCP-Guard Head-Only | 99.0 ± 0.6 | 98.8 ± 0.7 | 100.0 ± 0.0 | 99.4 ± 0.4 | 4.4 ± 2.6 | 6.4 ± 3.7 | 227.0 | 2.8 | 0.0 | 61.2 |
| Base E5 Full | 99.9 ± 0.2 | 99.9 ± 0.2 | 100.0 ± 0.0 | 100.0 ± 0.1 | 0.3 ± 0.7 | 0.5 ± 1.0 | 227.0 | 0.2 | 0.0 | 63.8 |
| Base E5 Head-Only | 97.8 ± 0.6 | 98.3 ± 0.7 | 98.9 ± 0.2 | 98.6 ± 0.4 | 6.2 ± 2.5 | 9.1 ± 3.6 | 224.6 | 4.0 | 2.4 | 60.0 |
| MCP-Guardian | 50.2 | 100.0 | 36.1 | 53.1 | 0.0 | 0.0 | 82 | 0 | 145 | 64 |

**Stage II alone**

| Model | Accuracy | Precision | Recall | F1 | FPR (all clean) | FPR (non-empty clean) | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 99.3 | 99.1 | 100.0 | 99.6 | 3.1 | 4.5 | 227 | 2 | 0 | 62 |
| MCP-Guard Full | 99.7 ± 0.2 | 99.6 ± 0.3 | 100.0 ± 0.0 | 99.8 ± 0.2 | 1.6 ± 1.1 | 2.3 ± 1.6 | 227.0 | 1.0 | 0.0 | 63.0 |
| MCP-Guard Head-Only | 99.0 ± 0.6 | 98.8 ± 0.7 | 100.0 ± 0.0 | 99.4 ± 0.4 | 4.4 ± 2.6 | 6.4 ± 3.7 | 227.0 | 2.8 | 0.0 | 61.2 |
| Base E5 Full | 99.9 ± 0.2 | 99.9 ± 0.2 | 99.9 ± 0.2 | 99.9 ± 0.1 | 0.3 ± 0.7 | 0.5 ± 1.0 | 226.8 | 0.2 | 0.2 | 63.8 |
| Base E5 Head-Only | 95.1 ± 0.8 | 98.2 ± 0.7 | 95.5 ± 0.6 | 96.8 ± 0.5 | 6.2 ± 2.5 | 9.1 ± 3.6 | 216.8 | 4.0 | 10.2 | 60.0 |
| MCP-Guardian | 50.2 | 100.0 | 36.1 | 53.1 | 0.0 | 0.0 | 82 | 0 | 145 | 64 |

### 5.3 Per category against the same 64 clean tools (precision / recall / F1)

**Stage I + II**

| Model | Credential Leakage: P / R / F1 | Instruction Tampering: P / R / F1 | Financial Loss: P / R / F1 |
|---|---:|---:|---:|
| Frozen MCP-Guard | 98.3 / 100.0 / 99.1 | 96.6 / 100.0 / 98.3 | 96.5 / 100.0 / 98.2 |
| MCP-Guard Full | 99.1 ± 0.6 / 100.0 ± 0.0 / 99.6 ± 0.3 | 98.3 ± 1.2 / 100.0 ± 0.0 / 99.1 ± 0.6 | 98.2 ± 1.2 / 100.0 ± 0.0 / 99.1 ± 0.6 |
| MCP-Guard Head-Only | 97.6 ± 1.4 / 100.0 ± 0.0 / 98.8 ± 0.7 | 95.4 ± 2.6 / 100.0 ± 0.0 / 97.6 ± 1.4 | 95.2 ± 2.7 / 100.0 ± 0.0 / 97.5 ± 1.4 |
| Base E5 Full | 99.8 ± 0.4 / 100.0 ± 0.0 / 99.9 ± 0.2 | 99.7 ± 0.8 / 100.0 ± 0.0 / 99.8 ± 0.4 | 99.6 ± 0.8 / 100.0 ± 0.0 / 99.8 ± 0.4 |
| Base E5 Head-Only | 96.6 ± 1.3 / 99.8 ± 0.4 / 98.2 ± 0.7 | 93.5 ± 2.4 / 100.0 ± 0.0 / 96.6 ± 1.3 | 93.0 ± 2.6 / 96.0 ± 0.8 / 94.5 ± 1.5 |
| MCP-Guardian | 100.0 / 67.8 / 80.8 | 100.0 / 7.0 / 13.1 | – / 0.0 / – |

**Stage II alone**

| Model | Credential Leakage: P / R / F1 | Instruction Tampering: P / R / F1 | Financial Loss: P / R / F1 |
|---|---:|---:|---:|
| Frozen MCP-Guard | 98.3 / 100.0 / 99.1 | 96.6 / 100.0 / 98.3 | 96.5 / 100.0 / 98.2 |
| MCP-Guard Full | 99.1 ± 0.6 / 100.0 ± 0.0 / 99.6 ± 0.3 | 98.3 ± 1.2 / 100.0 ± 0.0 / 99.1 ± 0.6 | 98.2 ± 1.2 / 100.0 ± 0.0 / 99.1 ± 0.6 |
| MCP-Guard Head-Only | 97.6 ± 1.4 / 100.0 ± 0.0 / 98.8 ± 0.7 | 95.4 ± 2.6 / 100.0 ± 0.0 / 97.6 ± 1.4 | 95.2 ± 2.7 / 100.0 ± 0.0 / 97.5 ± 1.4 |
| Base E5 Full | 99.8 ± 0.4 / 100.0 ± 0.0 / 99.9 ± 0.2 | 99.7 ± 0.8 / 100.0 ± 0.0 / 99.8 ± 0.4 | 99.6 ± 0.8 / 99.6 ± 0.8 / 99.6 ± 0.5 |
| Base E5 Head-Only | 96.6 ± 1.3 / 97.6 ± 0.7 / 97.1 ± 0.8 | 93.5 ± 2.4 / 100.0 ± 0.0 / 96.6 ± 1.3 | 92.3 ± 2.8 / 86.5 ± 1.0 / 89.3 ± 1.6 |
| MCP-Guardian | 100.0 / 67.8 / 80.8 | 100.0 / 7.0 / 13.1 | – / 0.0 / – |

Guardian flags nothing in Financial Loss, so its precision there is undefined (–).

### 5.4 By attack type (recall)

**Stage I + II**

| Model | P1 (n=43) | P2 (n=96) | P3 (n=88) |
|---|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 100.0 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| Base E5 Head-Only | 94.9 ± 1.0 | 100.0 ± 0.0 | 99.8 ± 0.5 |
| MCP-Guardian | 37.2 | 58.3 | 11.4 |

**Stage II alone**

| Model | P1 (n=43) | P2 (n=96) | P3 (n=88) |
|---|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 100.0 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| Base E5 Full | 99.5 ± 1.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| Base E5 Head-Only | 76.7 ± 2.8 | 100.0 ± 0.0 | 99.8 ± 0.5 |
| MCP-Guardian | 37.2 | 58.3 | 11.4 |

### 5.5 By test cell (recall)

| Model | known_server_new_cat (n=194) | new_server_new_cat (n=33) |
|---|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 |
| Base E5 Head-Only | 98.9 ± 0.2 | 99.4 ± 1.4 |
| MCP-Guardian | 39.7 | 15.2 |

### 5.6 Per seed (combined accuracy / F1 with clean / clean tools flagged)

**Stage I + II**

| Model | Seed 0 | Seed 1 | Seed 2 | Seed 3 | Seed 4 |
|---|---:|---:|---:|---:|---:|
| MCP-Guard Full | 100.0 / 99.6 / 2 | 100.0 / 99.8 / 1 | 100.0 / 99.8 / 1 | 100.0 / 100.0 / 0 | 100.0 / 99.8 / 1 |
| MCP-Guard Head-Only | 100.0 / 98.9 / 5 | 100.0 / 99.8 / 1 | 100.0 / 99.6 / 2 | 100.0 / 99.6 / 2 | 100.0 / 99.1 / 4 |
| Base E5 Full | 100.0 / 100.0 / 0 | 100.0 / 99.8 / 1 | 100.0 / 100.0 / 0 | 100.0 / 100.0 / 0 | 100.0 / 100.0 / 0 |
| Base E5 Head-Only | 99.1 / 98.3 / 6 | 98.7 / 98.5 / 4 | 98.7 / 98.2 / 5 | 99.1 / 98.9 / 3 | 99.1 / 99.1 / 2 |

**Stage II alone**

| Model | Seed 0 | Seed 1 | Seed 2 | Seed 3 | Seed 4 |
|---|---:|---:|---:|---:|---:|
| MCP-Guard Full | 100.0 / 99.6 / 2 | 100.0 / 99.8 / 1 | 100.0 / 99.8 / 1 | 100.0 / 100.0 / 0 | 100.0 / 99.8 / 1 |
| MCP-Guard Head-Only | 100.0 / 98.9 / 5 | 100.0 / 99.8 / 1 | 100.0 / 99.6 / 2 | 100.0 / 99.6 / 2 | 100.0 / 99.1 / 4 |
| Base E5 Full | 100.0 / 100.0 / 0 | 100.0 / 99.8 / 1 | 100.0 / 100.0 / 0 | 100.0 / 100.0 / 0 | 99.6 / 99.8 / 0 |
| Base E5 Head-Only | 96.0 / 96.7 / 6 | 95.2 / 96.6 / 4 | 94.7 / 96.2 / 5 | 95.6 / 97.1 / 3 | 96.0 / 97.5 / 2 |

### 5.7 Which stage decides, and which clean tools get flagged

Decisions on the 291 rows (Stage I + II). Stage I fires on 178 poisoned cases and on none of the 64 clean tools, identically for all five MCP-Guard variants, because Stage I is shared:

| Model | Decided by Stage I | Decided by Stage II | Empty description (auto-allow) |
|---|---:|---:|---:|
| Frozen MCP-Guard | 178 | 93 | 20 |
| MCP-Guard Full | 178.0 | 93.0 | 20.0 |
| MCP-Guard Head-Only | 178.0 | 93.0 | 20.0 |
| Base E5 Full | 178.0 | 93.0 | 20.0 |
| Base E5 Head-Only | 178.0 | 93.0 | 20.0 |

The most frequent Stage I rules on held-out cases are `shell_injection` (89), `important_tag` (76), `sensitive_file` (62), `shadow_hijack` (40) and `sql_injection` (15). A case can hit several rules.

Clean test tools flagged (Stage I + II):

| Model | Clean tools flagged, by server (summed over seeds) |
|---|---|
| Frozen MCP-Guard | Claude Post 1, BraveSearch 1 |
| MCP-Guard Full | Financial Dataset 4, Fetch 1 |
| MCP-Guard Head-Only | BraveSearch 5, Financial Dataset 5, Claude Post 4 |
| Base E5 Full | Claude Post 1 |
| Base E5 Head-Only | Financial Dataset 15, Claude Post 5 |
| MCP-Guardian | none |

What MCP Guardian caught, and with which rules:

| Risk category | Caught / n | Rules that fired (cases) |
|---|---:|---|
| Credential Leakage * | 78 / 115 | `ssh_key` 51, `env_secret` 18, `sensitive_file` 13 |
| Financial Loss * | 0 / 55 | none |
| Instruction Tampering * | 4 / 57 | `rm_rf` 3, `ssh_key` 1 |

### 5.8 Would Stage III have mattered?

Paper-mode Stage III only sees Stage II scores between 0.45 and 0.55:
- Frozen MCP-Guard: 0 of 291 held-out scores fall in that band. Every held-out poisoned case scores ≥ 0.995.
- The 20 fine-tuned checkpoints together: 16 of 5,420 scores fall in the band (0.3%), mostly from the head-only models.

Stage III could therefore change at most a handful of decisions.

## 6. Results on the whole test split (446 rows)

### 6.1 Precision, recall, F1, confusion matrix

**Stage I + II**

| Model | Accuracy | Precision | Recall | F1 | FPR (all clean) | FPR (non-empty clean) | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 99.6 | 99.5 | 100.0 | 99.7 | 3.1 | 4.5 | 382 | 2 | 0 | 62 |
| MCP-Guard Full | 99.8 ± 0.2 | 99.7 ± 0.2 | 100.0 ± 0.0 | 99.9 ± 0.1 | 1.6 ± 1.1 | 2.3 ± 1.6 | 382.0 | 1.0 | 0.0 | 63.0 |
| MCP-Guard Head-Only | 99.4 ± 0.4 | 99.3 ± 0.4 | 100.0 ± 0.0 | 99.6 ± 0.2 | 4.4 ± 2.6 | 6.4 ± 3.7 | 382.0 | 2.8 | 0.0 | 61.2 |
| Base E5 Full | 100.0 ± 0.1 | 99.9 ± 0.1 | 100.0 ± 0.0 | 100.0 ± 0.1 | 0.3 ± 0.7 | 0.5 ± 1.0 | 382.0 | 0.2 | 0.0 | 63.8 |
| Base E5 Head-Only | 98.5 ± 0.5 | 99.0 ± 0.4 | 99.3 ± 0.2 | 99.1 ± 0.3 | 6.2 ± 2.5 | 9.1 ± 3.6 | 379.4 | 4.0 | 2.6 | 60.0 |
| MCP-Guardian | 34.1 | 100.0 | 23.0 | 37.4 | 0.0 | 0.0 | 88 | 0 | 294 | 64 |

**Stage II alone**

| Model | Accuracy | Precision | Recall | F1 | FPR (all clean) | FPR (non-empty clean) | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 99.3 | 99.5 | 99.7 | 99.6 | 3.1 | 4.5 | 381 | 2 | 1 | 62 |
| MCP-Guard Full | 99.7 ± 0.2 | 99.7 ± 0.2 | 99.9 ± 0.1 | 99.8 ± 0.1 | 1.6 ± 1.1 | 2.3 ± 1.6 | 381.8 | 1.0 | 0.2 | 63.0 |
| MCP-Guard Head-Only | 99.0 ± 0.2 | 99.3 ± 0.4 | 99.5 ± 0.2 | 99.4 ± 0.1 | 4.4 ± 2.6 | 6.4 ± 3.7 | 380.2 | 2.8 | 1.8 | 61.2 |
| Base E5 Full | 99.9 ± 0.1 | 99.9 ± 0.1 | 99.9 ± 0.1 | 99.9 ± 0.1 | 0.3 ± 0.7 | 0.5 ± 1.0 | 381.8 | 0.2 | 0.2 | 63.8 |
| Base E5 Head-Only | 96.7 ± 0.7 | 98.9 ± 0.4 | 97.2 ± 0.5 | 98.1 ± 0.4 | 6.2 ± 2.5 | 9.1 ± 3.6 | 371.4 | 4.0 | 10.6 | 60.0 |
| MCP-Guardian | 34.1 | 100.0 | 23.0 | 37.4 | 0.0 | 0.0 | 88 | 0 | 294 | 64 |

### 6.2 By test cell (recall)

**Stage I + II**

| Model | known_server_new_cat (n=194) | new_server_known_cat (n=155) | new_server_new_cat (n=33) |
|---|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 100.0 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| Base E5 Head-Only | 98.9 ± 0.2 | 99.9 ± 0.3 | 99.4 ± 1.4 |
| MCP-Guardian | 39.7 | 3.9 | 15.2 |

**Stage II alone**

| Model | known_server_new_cat (n=194) | new_server_known_cat (n=155) | new_server_new_cat (n=33) |
|---|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 99.4 | 100.0 |
| MCP-Guard Full | 100.0 ± 0.0 | 99.9 ± 0.3 | 100.0 ± 0.0 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 98.8 ± 0.5 | 100.0 ± 0.0 |
| Base E5 Full | 99.9 ± 0.2 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| Base E5 Head-Only | 94.8 ± 0.6 | 99.7 ± 0.6 | 99.4 ± 1.4 |
| MCP-Guardian | 39.7 | 3.9 | 15.2 |

### 6.3 By risk category, all ten (recall; * = held out)

**Stage I + II**

| Model | Code Injection (n=9) | Credential Leakage * (n=115) | Data Tampering (n=19) | Financial Loss * (n=55) | Information Manipulation (n=43) | Infrastructure Damage (n=10) | Instruction Tampering * (n=57) | Message Hijacking (n=6) | Privacy Leakage (n=42) | Service Disruption (n=26) | **Combined (pooled)** | Unweighted mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | **100.0** | 100.0 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.0 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.0 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.0 |
| Base E5 Head-Only | 97.8 ± 5.0 | 99.8 ± 0.4 | 100.0 ± 0.0 | 96.0 ± 0.8 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **99.3 ± 0.2** | 99.4 ± 0.6 |
| MCP-Guardian | 0.0 | 67.8 | 0.0 | 0.0 | 0.0 | 0.0 | 7.0 | 0.0 | 14.3 | 0.0 | **23.0** | 8.9 |

**Stage II alone**

| Model | Code Injection (n=9) | Credential Leakage * (n=115) | Data Tampering (n=19) | Financial Loss * (n=55) | Information Manipulation (n=43) | Infrastructure Damage (n=10) | Instruction Tampering * (n=57) | Message Hijacking (n=6) | Privacy Leakage (n=42) | Service Disruption (n=26) | **Combined (pooled)** | Unweighted mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 96.2 | **99.7** | 99.6 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 99.2 ± 1.7 | **99.9 ± 0.1** | 99.9 ± 0.2 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 98.6 ± 1.3 | 95.4 ± 1.7 | **99.5 ± 0.2** | 99.4 ± 0.3 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 99.6 ± 0.8 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **99.9 ± 0.1** | 100.0 ± 0.1 |
| Base E5 Head-Only | 97.8 ± 5.0 | 97.6 ± 0.7 | 100.0 ± 0.0 | 86.5 ± 1.0 | 100.0 ± 0.0 | 98.0 ± 4.5 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **97.2 ± 0.5** | 98.0 ± 1.1 |
| MCP-Guardian | 0.0 | 67.8 | 0.0 | 0.0 | 0.0 | 0.0 | 7.0 | 0.0 | 14.3 | 0.0 | **23.0** | 8.9 |

### 6.4 By attack type (recall, Stage I + II)

| Model | P1 (n=56) | P2 (n=147) | P3 (n=179) |
|---|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 100.0 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| Base E5 Head-Only | 96.1 ± 0.8 | 100.0 ± 0.0 | 99.8 ± 0.3 |
| MCP-Guardian | 33.9 | 40.1 | 5.6 |

### 6.5 MCP Guardian rules on the whole test split

| Risk category | Caught / n | Rules that fired (cases) |
|---|---:|---|
| Credential Leakage * | 78 / 115 | `ssh_key` 51, `env_secret` 18, `sensitive_file` 13 |
| Financial Loss * | 0 / 55 | none |
| Instruction Tampering * | 4 / 57 | `rm_rf` 3, `ssh_key` 1 |
| Code Injection | 0 / 9 | none |
| Data Tampering | 0 / 19 | none |
| Information Manipulation | 0 / 43 | none |
| Infrastructure Damage | 0 / 10 | none |
| Message Hijacking | 0 / 6 | none |
| Privacy Leakage | 6 / 42 | `sensitive_file` 6 |
| Service Disruption | 0 / 26 | none |

## 7. Dev reference: val (seen categories, val servers)

**Stage I + II**

| Model | Accuracy | Precision | Recall | F1 | FPR (all clean) | FPR (non-empty clean) | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 92.7 | 91.4 | 100.0 | 95.5 | 32.7 | 32.7 | 171 | 16 | 0 | 33 |
| MCP-Guard Full | 93.2 ± 0.5 | 91.9 ± 0.5 | 100.0 ± 0.0 | 95.8 ± 0.3 | 30.6 ± 2.0 | 30.6 ± 2.0 | 171.0 | 15.0 | 0.0 | 34.0 |
| MCP-Guard Head-Only | 92.6 ± 0.2 | 91.3 ± 0.2 | 100.0 ± 0.0 | 95.5 ± 0.1 | 33.1 ± 0.9 | 33.1 ± 0.9 | 171.0 | 16.2 | 0.0 | 32.8 |
| Base E5 Full | 94.5 ± 0.2 | 93.3 ± 0.2 | 100.0 ± 0.0 | 96.6 ± 0.1 | 24.9 ± 0.9 | 24.9 ± 0.9 | 171.0 | 12.2 | 0.0 | 36.8 |
| Base E5 Head-Only | 93.3 ± 0.4 | 92.0 ± 0.4 | 100.0 ± 0.0 | 95.9 ± 0.2 | 30.2 ± 1.7 | 30.2 ± 1.7 | 171.0 | 14.8 | 0.0 | 34.2 |
| MCP-Guardian | 32.7 | 100.0 | 13.5 | 23.7 | 0.0 | 0.0 | 23 | 0 | 148 | 49 |

**Stage II alone**

| Model | Accuracy | Precision | Recall | F1 | FPR (all clean) | FPR (non-empty clean) | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 92.7 | 91.9 | 99.4 | 95.5 | 30.6 | 30.6 | 170 | 15 | 1 | 34 |
| MCP-Guard Full | 94.5 ± 1.0 | 93.5 ± 1.1 | 100.0 ± 0.0 | 96.6 ± 0.6 | 24.5 ± 4.3 | 24.5 ± 4.3 | 171.0 | 12.0 | 0.0 | 37.0 |
| MCP-Guard Head-Only | 92.6 ± 0.2 | 91.8 ± 0.2 | 99.4 ± 0.0 | 95.5 ± 0.1 | 31.0 ± 0.9 | 31.0 ± 0.9 | 170.0 | 15.2 | 1.0 | 33.8 |
| Base E5 Full | 99.7 ± 0.4 | 99.7 ± 0.5 | 100.0 ± 0.0 | 99.8 ± 0.3 | 1.2 ± 1.8 | 1.2 ± 1.8 | 171.0 | 0.6 | 0.0 | 48.4 |
| Base E5 Head-Only | 96.2 ± 0.4 | 96.1 ± 0.7 | 99.1 ± 0.5 | 97.6 ± 0.3 | 13.9 ± 2.7 | 13.9 ± 2.7 | 169.4 | 6.8 | 1.6 | 42.2 |
| MCP-Guardian | 32.7 | 100.0 | 13.5 | 23.7 | 0.0 | 0.0 | 23 | 0 | 148 | 49 |

Recall by category on val (Stage I + II):

| Model | Code Injection (n=8) | Data Tampering (n=17) | Information Manipulation (n=40) | Infrastructure Damage (n=27) | Message Hijacking (n=7) | Privacy Leakage (n=42) | Service Disruption (n=30) | **Combined (pooled)** | Unweighted mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | **100.0** | 100.0 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.0 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.0 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.0 |
| Base E5 Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | **100.0 ± 0.0** | 100.0 ± 0.0 |
| MCP-Guardian | 100.0 | 35.3 | 7.5 | 0.0 | 0.0 | 14.3 | 0.0 | **13.5** | 22.4 |

Clean val tools flagged (Stage I + II): the false positives come from two servers, Commander (via Stage I rules) and Codacy (via Stage II):

| Model | Clean tools flagged, by server (summed over seeds) |
|---|---|
| Frozen MCP-Guard | Commander 12, Codacy 4 |
| MCP-Guard Full | Commander 60, Codacy 15 |
| MCP-Guard Head-Only | Commander 60, Codacy 20, wechat 1 |
| Base E5 Full | Commander 61 |
| Base E5 Head-Only | Commander 65, Codacy 9 |
| MCP-Guardian | none |

## 8. val → held-out → whole test

**Stage I + II**

| Model | Recall val | Recall held-out | Recall test | F1 val | F1 held-out | F1 test | FPR val (49 clean) | FPR test (64 clean) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 100.0 | 100.0 | 100.0 | 95.5 | 99.6 | 99.7 | 32.7 | 3.1 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 95.8 ± 0.3 | 99.8 ± 0.2 | 99.9 ± 0.1 | 30.6 ± 2.0 | 1.6 ± 1.1 |
| MCP-Guard Head-Only | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 95.5 ± 0.1 | 99.4 ± 0.4 | 99.6 ± 0.2 | 33.1 ± 0.9 | 4.4 ± 2.6 |
| Base E5 Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 | 96.6 ± 0.1 | 100.0 ± 0.1 | 100.0 ± 0.1 | 24.9 ± 0.9 | 0.3 ± 0.7 |
| Base E5 Head-Only | 100.0 ± 0.0 | 98.9 ± 0.2 | 99.3 ± 0.2 | 95.9 ± 0.2 | 98.6 ± 0.4 | 99.1 ± 0.3 | 30.2 ± 1.7 | 6.2 ± 2.5 |
| MCP-Guardian | 13.5 | 36.1 | 23.0 | 23.7 | 53.1 | 37.4 | 0.0 | 0.0 |

**Stage II alone**

| Model | Recall val | Recall held-out | Recall test | F1 val | F1 held-out | F1 test | FPR val (49 clean) | FPR test (64 clean) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen MCP-Guard | 99.4 | 100.0 | 99.7 | 95.5 | 99.6 | 99.6 | 30.6 | 3.1 |
| MCP-Guard Full | 100.0 ± 0.0 | 100.0 ± 0.0 | 99.9 ± 0.1 | 96.6 ± 0.6 | 99.8 ± 0.2 | 99.8 ± 0.1 | 24.5 ± 4.3 | 1.6 ± 1.1 |
| MCP-Guard Head-Only | 99.4 ± 0.0 | 100.0 ± 0.0 | 99.5 ± 0.2 | 95.5 ± 0.1 | 99.4 ± 0.4 | 99.4 ± 0.1 | 31.0 ± 0.9 | 4.4 ± 2.6 |
| Base E5 Full | 100.0 ± 0.0 | 99.9 ± 0.2 | 99.9 ± 0.1 | 99.8 ± 0.3 | 99.9 ± 0.1 | 99.9 ± 0.1 | 1.2 ± 1.8 | 0.3 ± 0.7 |
| Base E5 Head-Only | 99.1 ± 0.5 | 95.5 ± 0.6 | 97.2 ± 0.5 | 97.6 ± 0.3 | 96.8 ± 0.5 | 98.1 ± 0.4 | 13.9 ± 2.7 | 6.2 ± 2.5 |
| MCP-Guardian | 13.5 | 36.1 | 23.0 | 23.7 | 53.1 | 37.4 | 0.0 | 0.0 |

Recall on held-out categories is as high as on val for every learned model. Only Base E5 Head-Only drops: by 1.1 points with Stage I + II and by 3.6 with Stage II alone. F1 rises from val to test only because FPR falls, and FPR falls because the clean tools come from different servers (Section 9).

## 9. Answers to the analysis questions

1. **Which model has the highest combined held-out accuracy?** Four models tie at 100%: Frozen MCP-Guard, MCP-Guard Full, MCP-Guard Head-Only and Base E5 Full. Once clean tools count, **Base E5 Full** is best: F1 100.0 ± 0.1, 0.2 of 64 clean tools flagged. MCP-Guard Full flags 1.0, Frozen 2, MCP-Guard Head-Only 2.8 and Base E5 Head-Only 4.0. These gaps are 1–4 tools out of 64, within the uncertainty in Section 4.
2. **Full or head-only fine-tuning?** Full fine-tuning is at least as good everywhere.
   - Base E5 Head-Only is the only learned model that misses held-out attacks: 2.4 per seed with Stage I + II, 10.2 with Stage II alone. Almost all of its misses are P1 cases, mostly Financial Loss (Stage II alone P1 recall 76.7%).
   - It also has the highest FPR (6.2%).
   - MCP-Guard Head-Only flags more clean tools than MCP-Guard Full (2.8 vs 1.0).
3. **MCP-Guard's security-trained encoder vs base E5?**
   - Without any MCPTox training, MCP-Guard's encoder already reaches 100% held-out recall.
   - With the encoder frozen (head-only), MCP-Guard's encoder beats E5: Stage II alone recall 100% vs 95.5%, FPR 4.4% vs 6.2%.
   - With full fine-tuning the two converge, and E5 Full ends up with the fewest false positives.
   - So the security pre-training helps most when the encoder can't be updated.
   - *Across the 8 other held-out combinations this does not hold: E5 Head-Only averages 98.4% vs 95.8% for MCP-Guard Head-Only (Stage II alone), and MCP-Guard's encoder catches only ~75% of held-out Infrastructure Damage. See the full summary at the top and [COMBOS_RESULTS.md](COMBOS_RESULTS.md).*
4. **Rule-based MCP Guardian vs learned classifiers?** Guardian never flags a clean tool, with precision 100% wherever it flags anything. But it catches only 36.1% of held-out attacks and 23.0% of the whole test split.
   - What it catches depends on topic overlap with its 11 rules. Credential Leakage (67.8%) comes almost entirely from `ssh_key`, `env_secret` and `sensitive_file`.
   - Financial Loss (0%) matches no rule at all. Neither do 6 of the 7 seen categories on the test split (Section 6.5); on val it does catch Code Injection and some Data Tampering (Section 7).
   - Its higher score on held-out (36.1%) than on val (13.5%) reflects which categories its rules happen to cover. It is not generalization.
5. **Which held-out category is hardest?** **Financial Loss**: 0% for Guardian, 96.0% for Base E5 Head-Only (86.5% with Stage II alone), and the source of most head-only misses. Instruction Tampering is hard only for Guardian (7.0%). Credential Leakage is the easiest for Guardian (67.8%), and every learned model scores 99.8–100% on both Credential Leakage and Instruction Tampering.

## 10. Why these numbers do not show strong generalization

- **Shared templates.** Stage I alone blocks 178 of 227 held-out cases, mostly through the `shell_injection` and `important_tag` rules, the same template cues it fires on in training data. A category label changes *what* an attack asks for, not *how* MCPTox phrases it.
- **No training needed.** MCP-Guard as released, never trained on MCPTox, scores the same 100% as models trained on it. The category split therefore can't distinguish learning attacks from recognizing the template.
- **The FPR change is a server effect.** FPR falls from ~25–33% on val to ~0–6% on test because the clean tools come from different servers: Commander and Codacy on val; Claude Post, BraveSearch and Financial Dataset on test. It says nothing about categories.
- **Small, partly empty clean set.** There are only 64 clean test tools, 20 of them with empty descriptions, and MCP-Guard allows those automatically. The FPR over non-empty tools is about 1.5× higher.
- **Length shortcut not ruled out.** Clean descriptions are much shorter than poisoned ones (median 14 vs 60 tokens on `tune`). A length-matched check is still open.
- **Test split now used.** The whole test split has been scored, so no untouched test data remains for a later "final" run.

**Conclusion for the paper:** on MCPTox, held-out categories are close to in-distribution for every learned detector. Report this result as an upper bound. The generalization claim should rest on Experiment 2 (rewritten attacks) and Experiment 3 (live servers).

## 11. Files and reproduction

| What | Where |
|---|---|
| This analysis | `experiments/rq1_heldout/RESULTS.md` |
| Code, tests, CARC jobs | `experiments/rq1_heldout/{evaluate.py,report.py,test_evaluate.py,carc/}` |
| Generated tables | `results/rq1_heldout/report.md` (held-out), `results/rq1_heldout/report_test.md` (whole test) |
| Per-category (all 10 categories), untrained-on-all-MCPTox and cross-dataset tables, committed | [tables/TABLES.md](tables/TABLES.md) and `tables/*.csv` (`category_summary.py`) |
| Cross-dataset raw outputs (gitignored) | `results/mcp_guard/upstream_dev_eval/` (`detectors/mcp_guard/eval_upstream_dev.py`) |
| Per model and configuration (seed mean ± std) | `results/rq1_heldout/<split>/summary.{csv,json}` |
| Per run, including each seed | `results/rq1_heldout/<split>/runs.csv` |
| Per run detail: checkpoint, counts, metrics, confusion matrix, time, errors | `results/rq1_heldout/<split>/<model>/<config>[_seed<k>]/{metrics.json,log.txt}` |
| Sample-level predictions (case ID, label, prediction, stage, score, rules; no text) | `.../predictions.jsonl` |
| Checkpoints | CARC `/project2/xiangren_1987/group_12/checkpoints/mcp_guard/` (20 × 1.1 GB; too large for GitHub) |

`results/` is gitignored, per the team rule. Rerun with the commands in [README.md](README.md). `<split>` is `heldout`, `test` or `val`.
