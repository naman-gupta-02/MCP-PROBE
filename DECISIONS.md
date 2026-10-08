# Decisions

| Date | Decision | Why |
|---|---|---|
| 2026-10-08 | Python 3.11, managed with `uv` (`pyproject.toml` + committed `uv.lock`). | Reproducible environments across 6 machines; 3.11 is widely supported by ML/agent libraries. |
| 2026-10-08 | Folder layout: `configs/ data/{raw,splits,processed}/ detectors/ proxy/ servers/ attacker/ agent/ experiments/ results/ scripts/ tests/`. | One folder per area so each person works on a separate branch with few conflicts; raw/processed data and results are gitignored. |
| 2026-10-08 | Split rule: 3 held-out risk categories + servers split train(30)/val(6)/test(9) per `data/splits/server_split.json`. tune = train server & known category; val = val server & known category; test = test server OR held-out category, tagged with `test_cell`. Clean tools split by server only. | Lets Experiment 1 measure generalization to both new servers and new risk categories, and their combination, while tuning only on dev data. |
| 2026-10-08 | Test-data guard: `load_cases("test")` raises unless `FINAL_EVAL=1`. | Prevents accidentally tuning prompts/rules/thresholds on held-out data. |
| 2026-10-08 | MCPTox `metadata.paradigm` `Template-N` is stored as `PN` (P1/P2/P3). | Team confirmed the mapping; the dataset itself only says `Template-N`. |
| 2026-10-08 | Drop the 36 poisoned cases with `wrong_data = 2`; keep 1,312. | Flagged by the MCPTox authors; the remaining count matches the paper's 1,312. |
| 2026-10-08 | Clean tools come from each server's `tool_names` (353 total), with descriptions from `clean_system_promot`; empty or literal `None` descriptions become `null`. Apify uses its 7 listed tools, not the 16 in its prompt. | `tool_names` matches the 353 clean tools reported; never invent text. |
| 2026-10-08 | `description` stores only the `Description:` text of a tool block (literal `\n` escapes normalized). Servers are matched on `server_name` (`GitHub`/`GitLab`), not the dict keys (`Github`/`Gitlab`). | Detectors see the description text; `server_name` matches our split file exactly. |
| 2026-10-08 | Clean tools on test servers get `test_cell = new_server_clean`. | Every test row needs a test cell; the three poisoned cells don't apply to clean tools. |
