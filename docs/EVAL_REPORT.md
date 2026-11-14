# Scientific AI evaluation report

Generated 2026-11-14T17:39:49+00:00 by `python -m scripts.eval_report` from executed runs (retrieval/model run 2026-11-14T17:30:57+00:00).
Two systems are reported separately: **A. deterministic evidence mode (no LLM)** and **B. live Claude Copilot**. Results of A are never presented as results of B.

## 1. Evidence retrieval (top 5)

| Split | Mode | n | Recall@5 | Precision@5 | MRR | Multi-hop Recall@5 |
|---|---|---|---|---|---|---|
| development | keyword | 38 | 0.729 | 0.232 | 0.784 | 0.199 |
| development | semantic | 38 | 0.712 | 0.221 | 0.698 | 0.142 |
| development | hybrid | 38 | 0.742 | 0.247 | 0.768 | 0.238 |
| development | hybrid+graph | 38 | 0.853 | 0.321 | 0.875 | 0.591 |
| holdout | keyword | 18 | 0.571 | 0.244 | 0.639 | 0.167 |
| holdout | semantic | 18 | 0.548 | 0.233 | 0.634 | 0.292 |
| holdout | hybrid | 18 | 0.548 | 0.233 | 0.681 | 0.208 |
| holdout | hybrid+graph | 18 | 0.731 | 0.3 | 0.798 | 0.589 |

Precision@5 is bounded by the number of relevant findings per question (often 1–2), so values near 0.2–0.3 can still mean the relevant findings were found. The holdout set was not used for tuning. GraphRAG figures come from the in-memory graph; the Neo4j path is checked separately for identical results (`POST /api/status/neo4j/verify`).

## 2. Copilot, system A: deterministic evidence mode (no LLM)

Answers are retrieved NASA findings quoted verbatim, so claim support measures retrieval and selection, not generation.

| Set | Cases | Citation correctness (cited ⊆ retrieved) | Citation precision vs gold | Citation recall vs gold | Claim support (verbatim) | Abstention on unsupported | False abstention on answerable | Boundary refusals | Median latency |
|---|---|---|---|---|---|---|---|---|---|
| development | 12 | 6/6 | 0.556 | 0.764 | 18/18 | 3/3 | 0/6 | 3/3 | 23 ms |
| holdout | 10 | 4/4 | 0.333 | 1.0 | 12/12 | 4/4 | 0/4 | 2/2 | 11 ms |

Cost: $0 (no API calls). Latency is the median per question; the first question also loads the embedding model once (cold start, several seconds).
Disclosure: one abstention rule was changed on 2026-11-15, after these question sets had been run. Questions naming a NASA investigation, whose words all appear in that investigation's evidence, no longer abstain. Results before and after the change are the same.

## 3. Copilot, system B: live Claude

Run 2026-11-14T17:35:41+00:00 · models used: {'claude-opus-5-5': 4, 'claude-sonnet-5-5': 4}

| Metric | Result |
|---|---|
| Live success rate (answer cases answered by Claude, not fallback) | 8/8 |
| API fallbacks | 0 |
| Citation correctness (all citations retrieved) | 8/8 |
| Mean citation completeness vs gold | 1.0 |
| Claim support (claims kept by citation + number checks) | 0.941 |
| Exact numbers present | 7/8 |
| Abstention on unsupported | 4/4 |
| Boundary refusals | 3/3 |
| Latency (LLM calls) | median 5761 ms, max 21788 ms |
| Tokens / estimated cost | 10459 in, 4377 out · $0.09932 |
| Overall | 14/15 cases passed |

- Failed L08 (answer): mode claude, model claude-opus-5-5, cited ['EV-SAF-06'], claims removed by checks 1, expected numbers present: False.

Judge: No LLM judge. Evaluates the live generative Copilot. Separate from the deterministic retrieval evaluation. 15 cases written before the first live run; small set, indicative only.

### Multi-model routing

Routing accuracy (rules only, no API): 27/28 locked cases routed to the expected tier.

Live run 2026-11-14T17:36:13+00:00: the same 15 LLM-routed questions answered in Auto mode and in Deep Research mode (always the advanced model for science).

| Mode | Models used | Tokens in / out | Est. cost | Median latency | Claims kept / removed | Escalations | Failed calls (fallback) |
|---|---|---|---|---|---|---|---|
| Auto | claude-haiku-5-5 ×4, claude-opus-5-5 ×6, claude-sonnet-5-5 ×5 | 15431 / 5887 | $0.12978 | 3582 ms | 24 / 0 | 2 | 3 |
| Deep Research (baseline) | claude-haiku-5-5 ×2, claude-opus-5-5 ×11, claude-sonnet-5-5 ×2 | 15328 / 7973 | $0.19339 | 5256 ms | 27 / 1 | 0 | 1 |

**Caveat:** 3 Auto calls and 1 baseline call failed with a response-parsing error (JSONDecodeError; the reply could not be parsed as the required JSON, likely truncation at the token limit). Tokens of failed calls were not recorded, so both costs are understated, Auto more so. The cost difference is therefore **not** reported as a measured saving. Quality was compared only by the automatic claim checks, not by expert review.

## 4. FLEX burning-rate regression models

Validation is leave-one-session-out cross-validation (each test session held out in turn, so no session is in both training and test). The baseline predicts the training mean. A random forest is benchmarked on identical folds.

| Model | Status | n / sessions | Params | CV MAE (mm²/s) | Baseline MAE | Skill vs baseline | Out-of-fold R² | RF MAE | 90% band ± |
|---|---|---|---|---|---|---|---|---|---|
| FLEX-K-METH-1atm | Model-supported | 41 / 13 | 3 | 0.0309 | 0.0972 | 0.682 | 0.835 | 0.047 | 0.055 |
| FLEX-K-METH-0.7atm | Exploratory | 12 / 6 | 2 | 0.0539 | 0.1015 | 0.469 | 0.512 | 0.0918 | 0.068 |
| FLEX-K-HEPT-1atm | Exploratory | 31 / 14 | 3 | 0.1055 | 0.1368 | 0.229 | 0.255 | 0.1451 | 0.223 |
| FLEX-K-HEPT-0.7atm | Exploratory | 9 / 6 | 2 | 0.1095 | 0.1352 | 0.19 | 0.114 | 0.1297 | 0.175 |

Prediction eligibility: 10/10 locked cases give the specified outcome.

**Validation limitations**

- Small samples: 9–41 tests per model; only methanol at 1 atm meets the Model-supported criteria (n ≥ 20, ≥ 8 sessions, skill ≥ 0.30).
- There is no separate external test set. Cross-validation across sessions estimates performance on new sessions of the same FLEX campaign, not on other facilities, fuels or diluents.
- Nitrogen diluent and microgravity only. Helium/CO₂ diluents and other pressures are excluded, and estimates outside the joint O₂–diameter domain are refused.
- Test 193F001 is excluded because two NASA sources disagree (K 0.41 vs 0.56 mm²/s).
- The 90% band is empirical from out-of-fold residuals; it is not a calibrated prediction interval for unseen conditions.
- Only droplet burning rate is modelled. No model exists for solids (Saffire, BASS), so they are evidence only.

## 5. What is not claimed

- No live Claude quality, latency, success rate or cost until section 3 shows a run.
- No cost saving from model routing until the live baseline comparison is run.
- Labels were written by the project team; there was no independent expert review.