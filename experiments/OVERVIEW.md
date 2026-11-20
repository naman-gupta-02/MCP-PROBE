# MCP-PROBE: results overview

We test whether existing MCP tool-poisoning detectors — **MCP-Guard** (arXiv 2508.10991) and
**MCP Guardian** (arXiv 2504.12757) — still work outside the conditions they were built for. We do
not build a new detector. All attacks come from the **MCPTox** benchmark (arXiv 2508.14925).

## The thesis in one line

Existing detectors look strong when measured statically (RQ1), but that strength is fragile: a cheap
LLM can reword a caught attack to evade them (RQ2), and even when a detector *does* catch an attack
against a live agent, it protects bluntly — at a steep cost to the agent's real task (RQ3).

## The three research questions

| | Question | Finding | Details |
|---|---|---|---|
| **RQ1** | Do detectors catch attacks from risk categories they were never tuned on? | **Yes, statically** — the learned detectors hit ~100% recall / ~99 F1 on held-out categories; the keyword baseline (Guardian) does not generalize (36% recall). | [rq1_heldout/RESULTS.md](rq1_heldout/RESULTS.md) |
| **RQ2** | Can a cheap LLM reword a caught poisoned description to evade the detector while keeping the attack? | **Yes** — up to **28%** of caught attacks evade (gpt-oss-20b), concentrated in semantic categories; **0%** on Code Injection (hard literals can't be paraphrased); detector feedback barely helps. | [rq2_adaptive/RESULTS.md](rq2_adaptive/RESULTS.md) |
| **RQ3** | Against a live agent, does a detector actually stop the attack, and at what cost? | **MCP-Guard stops 100% of attacks but halves task-success (41%) and false-blocks 58%** — it can't tell "block the malicious tool" from "the user needed that tool" (worst on P1). **Guardian barely protects** (66% attacks still land). | [rq3_live/RESULTS.md](rq3_live/RESULTS.md) |

## Supporting study: length bias

A confound check for RQ1: MCPTox clean descriptions are ~5× shorter than poisoned ones, so a detector
could be keying on **length**, not content. Length-matching the clean tools and retraining shows
length *was* a real shortcut (a length-only rule's false positives jump 30%→77%), but retraining on
length-controlled data debiases the classifier (Base E5 Full: 100% recall at 0% classifier false
positives). So the RQ1 numbers should be read with length controlled. See
[clean_padding/README.md](clean_padding/README.md).

## How the three fit together

- **RQ1** establishes the baseline: these detectors look nearly solved.
- **RQ2** shows that is an illusion under a cheap adaptive attacker — strongest exactly on the
  semantic attacks where RQ1 looked best.
- **RQ3** shows the other half of the cost: where a detector *does* catch an attack live, the
  protection is blunt (MCP-Guard) or largely absent (Guardian). The useful signal is the
  **security/utility trade-off**, not a single recall number.

Shared judging note: RQ2 judges *text* (did the reworded description still carry the attack — an LLM
reading), while RQ3 judges *behavior* (did the agent actually perform the malicious tool call — a
deterministic rule over the call log). RQ3 is the one that confirms an agent is really tricked.

## Open items

- RQ2: hand-verify a sample of the 231 "preserved" evasions (the qwen judge is a proxy).
- Experiment 1: a neutral cross-dataset check on MCP-SafetyBench (arXiv 2512.15163 [verify]).
- Final report + presentation stitching all of the above together.
