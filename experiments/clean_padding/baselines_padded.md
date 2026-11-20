# Baseline detectors: original vs length-padded clean data

Non-learned baselines. `length_only` threshold is tuned on `tune` (balanced accuracy); the same threshold is applied to both the original and padded evaluation so the effect of padding is visible.

## val

| Baseline | Recall orig | Recall padded | FPR orig | FPR padded | F1 orig | F1 padded |
|---|---:|---:|---:|---:|---:|---:|
| block_everything | 100.0 | 100.0 | 100.0 | 100.0 | 87.5 | 87.5 |
| length_only | 100.0 | 100.0 | 61.2 | 100.0 | 91.9 | 87.5 |
| keyword_only | 87.7 | 87.7 | 0.0 | 0.0 | 93.5 | 93.5 |

(length_only threshold tuned on ORIGINAL tune: 106 chars)

## held-out categories (+clean test)

| Baseline | Recall orig | Recall padded | FPR orig | FPR padded | F1 orig | F1 padded |
|---|---:|---:|---:|---:|---:|---:|
| block_everything | 100.0 | 100.0 | 100.0 | 100.0 | 91.2 | 91.2 |
| length_only | 96.9 | 96.9 | 29.5 | 77.3 | 95.7 | 91.5 |
| keyword_only | 86.8 | 86.8 | 0.0 | 0.0 | 92.9 | 92.9 |

(length_only threshold tuned on ORIGINAL tune: 106 chars)
