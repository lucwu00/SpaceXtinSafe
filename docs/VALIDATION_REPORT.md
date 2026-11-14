# SpaceXtinsafe scientific validation report

Run date: 15 Nov 2026 (server clock 14 Nov, UTC). Every figure here comes from an executed run, and the raw results are in `backend/eval/validation/`.

This is an internal evaluation. The build assistant wrote the questions, cases and reference labels; nobody independent reviewed them, and NASA has not endorsed or certified anything here.

**Reproduce (from `backend/`):**

```
python -m scripts.validate_science                                   # gap benchmark, regression, holdout-2, impact proxy
SPACEXI_SEMANTIC=0 python -m scripts.validate_science --tag deployed-config --only holdout2,gaps
python -m scripts.validate_science --only holdout2 --live            # live Claude run, needs ANTHROPIC_API_KEY
python scripts/check_deployed.py https://spacextinsafe.onrender.com  # deployed end-to-end check
```

**Frozen inputs.** Each one was hash-locked before its first run, and the script refuses to run if a hash changes.

| File | Lock | SHA-256 (first 12) |
|---|---|---|
| `eval/gap_benchmark.json` | `GAPS.lock` | 417a7b96d3bb |
| `eval/holdout2_copilot.json` | `HOLDOUT2.lock` | 0083774130a6 |
| `eval/impact_tasks.json` | `IMPACT.lock` | 0f30a08fb5c9 |

## Evaluation kinds

| Kind | What it means here |
|---|---|
| DETERMINISTIC | Computed by the app's own code with no LLM call (gap logic, models, retrieval, evidence-mode Copilot) |
| LIVE | Calls Claude or Neo4j at run time. Only `check_deployed.py` (against Render) and `--live` do this |
| RECORDED | Stored results from an earlier live run, such as `results_claude_live.json` (14/15, 14 Nov) |
| PROXY | An automated stand-in for a human measurement (see `IMPACT_EVALUATION.md`) |

## 1. End-to-end integration (P0)

`scripts/check_deployed.py` runs 23 checks with inputs generated at run time:
- health and status
- Neo4j verification
- 3 live Claude questions
- a custom spacecraft with a random atmosphere
- custom-material handling, including the alias-collision check
- 5 prediction requests, one supported and four unsupported
- gaps and interactions
- PDF generated twice
- boundary, abstention and tool routing
- stored results, the usage log, and cleanup

| Run | Deterministic | Live Claude | Live Neo4j | Recorded |
|---|---|---|---|---|
| Local backend (no API key, no Neo4j), 14 Nov 21:20 UTC | **18/18** | 0/3 (expected: no key) | 0/1 (expected: not configured) | 1/1 |
| Render, before the fixes were deployed (14 Nov 21:44 UTC) | 15/18 | 2/3 | 1/1 | 1/1 |
| **Render, after the fixes were deployed (14 Nov 21:56 UTC)** | **18/18** | **2/3** | **1/1** | **1/1** |

The deployed run (22/23) confirms on Render:
- Neo4j AuraDB retrieval matches the in-memory graph (`verified: true`).
- Claude answers live with checked citations, including the sleeping-bag question via the knowledge graph.
- All deterministic paths pass.

The first Render run reproduced the alias bug live: check 9 failed, and that also broke check 16. Both pass after the fix.

The one remaining failure is check 6, the conflicting-evidence question. On the earlier Render run Claude cited the conflict finding EV-SAF-06; on this run (served from a cached answer created after the redeploy) it cited EV-SAF-05 and EV-SAF-07 only. The conflict findings are supplied to Claude, but whether it cites them varies between runs. Treat this as a known variability, not a pass.

## 2. Research-gap benchmark (P0)

The benchmark has 30 frozen cases:
- 17 material and condition cells
- 4 interaction pairs plus 1 documented pair
- 3 custom-material cases
- 3 out-of-domain prediction requests

The reference labels were assigned by hand from the curated finding fields and the PSI-69 table.

| Metric | Result |
|---|---|
| Gap detection precision (27 detection cases) | **17/17 = 1.00** (0 false gaps) |
| Gap detection recall | **17/17 = 1.00** (0 missed gaps) |
| Classification accuracy (9 classes) | **30/30** after fix (29/30 before; see G20) |
| Out-of-model-domain requests refused | 3/3 |
| Absence caveat shown with every output | 30/30 |
| Outputs implying safety from missing evidence | 0/30 |
| Gaps that received a proposal | 17/17 |
| Proposals shown for a non-gap | 1 (G21: methanol at 18–23% O₂ has PSI-69 tests and a model-supported estimate, but the cell still shows the generic "to close a gap" text) |
| Proposal relevance, text only (4-item rubric) | 0.65 mean. Condition-gap text scores 0.50 (generic: names neither the material nor the band); interaction text scores 0.75 (names conditions, not materials) |
| Proposal relevance in UI context | 1.00 (the cell or Fire Lab panel shows the material and band beside the text) |

**Library gap vs literature gap.** For 2 of the 17 reference gaps, NASA publications report related data that was never curated into the library:
- **G02, PMMA at partial gravity:** LUCI flew a 4 mm PMMA rod (LUCI deck p.4).
- **G11, PMMA in quiescent flow:** the BASS-II appendix has slow-flow PMMA burns (TM-20210011385 p.135).

The system can only say "no finding in **this** library". It cannot detect literature outside its curation. The wording is correct, but the slides must not call these confirmed literature gaps.

**Defect found and fixed (G20).** A user-defined material with the alias "PMMA" took over the name, and PMMA lost all 9 of its findings until the user material was deleted. Catalogue names now take precedence (`data.material_aliases`).

## 3. Copilot holdout-2 (P1)

There are 23 questions, written from passages of the original NASA publications (file and page per question) and frozen before the run:

| Type | Count |
|---|---|
| Direct | 3 |
| Numerical | 6 |
| Multi-hop | 3 |
| Limitation | 3 |
| Literature-only (the fact is in a publication but not in the library) | 5 |
| Unsupported or boundary | 3 |

**Retrieval** (15 answerable questions):

| Mode | Recall@5 | Precision@5 | MRR |
|---|---|---|---|
| keyword | 1.00 | 0.27 | 0.97 |
| semantic | 1.00 | 0.27 | 0.93 |
| hybrid / hybrid+graph | 1.00 | 0.27 | 0.97 |

Recall is at ceiling because most of these questions have one or two relevant findings, so this set does not separate the retrieval modes. Precision@5 is capped at about 0.3 for the same reason. Deployed configuration (semantic off): keyword-only, with the same results.

**Copilot, deterministic (evidence mode, no LLM):**

| Measure | Result |
|---|---|
| Answerable questions answered, citing a relevant finding | **14/15** |
| Citations within the retrieved set | 14/14 |
| Required numbers present | 8/8 |
| Unsupported or boundary (Kapton at Mars g abstained, verdict refused, emergency refused) | **3/3** |
| Literature-only questions abstained | **0/5** (see failures) |
| Safety verdicts in any answer | 0 |

**Copilot, live Claude** (run by the team on 15 Nov, semantic off as on Render; raw results in `eval/validation/holdout2_live.json`):

| Measure | Result |
|---|---|
| Overall | **20/23** |
| Answerable questions answered live by Claude | 14/15 |
| Citations within the retrieved set | 14/14 |
| Cited a relevant finding | 13/14 |
| Required numbers present | 7/8 |
| Literature-only questions declined | **4/5** (evidence mode: 0/5) |
| Unsupported or boundary refused | 3/3 |
| Claim support (claims kept after citation and number checks) | 0.893 |
| Safety verdicts in any answer | 0 |

The three live failures:
- **H2-01:** the same "paper" false abstention as in evidence mode.
- **H2-06:** cited the related Apollo 204 finding EV-AP1-01 instead of EV-AP1-02, so "16.5 psia" was missing.
- **H2-20:** the LUCI sample-size question, a fact not in the library, was answered from the related EV-LUCI-01 finding instead of being declined.

## 4. Regression validation (P1)

The grouped validation is unchanged: leave-one-session-out, where a session is a test date. Thresholds are unchanged. The bootstrap resamples sessions 2,000 times.

| Model | n / sessions | MAE (95% CI) | Skill (95% CI) | Mean residual (95% CI) | 90% band: in-sample / cross-conformal |
|---|---|---|---|---|---|
| Methanol 1 atm (model-supported) | 41 / 13 | 0.031 (0.022–0.043) | **0.68 (0.54–0.78)** | +0.001 (−0.011 to 0.010) | 0.90 / **0.88** |
| Methanol 0.7 atm (exploratory) | 12 / 6 | 0.054 (0.028–0.079) | 0.47 (−0.10 to 0.78) | −0.010 | 0.83 / 0.92 |
| n-Heptane 1 atm (exploratory) | 31 / 14 | 0.105 (0.068–0.151) | 0.23 (−0.04 to 0.45) | +0.005 | 0.90 / 0.87 |
| n-Heptane 0.7 atm (exploratory) | 9 / 6 | 0.109 (0.064–0.162) | 0.19 (−0.06 to 0.44) | +0.040 | 0.89 / 0.78 |

Units are mm²/s.

**Interpretation:**
- **No systematic bias.** Every bias CI includes 0.
- **Exploratory status is supported.** The three exploratory models have skill CIs that include 0.
- **The band slightly under-covers.** The methanol 1 atm band covers 36/41 held-out tests (0.88) when built only from other sessions, against a nominal 0.90. The small heptane 0.7 atm group covers 0.78. This supports calling it an empirical band, not a calibrated interval.
- **Sensitivity is stable.** For methanol 1 atm, K rises 0.0183 mm²/s per O₂ point, and the slope ranges 0.0176–0.0187 across folds (sign stable in every fold for all four models). D0 changes K by −0.027 per 0.5 mm.

**Out-of-domain grid** (methanol 1 atm; 1,058 points from 5–50% O₂ and 0.5–6 mm):
- Outside the tested ranges: 0 model-supported estimates, 797 refused, 90 **exploratory**. The exploratory points sit up to 4 O₂ points (8–11%, 31–33%) or about 0.3 mm beyond the tested ranges.
- Inside: 67 model-supported, 93 exploratory, 11 refused.

Showing those 90 outside points as labelled exploratory estimates is the current rule (outside the hull but near tested points). That is a design limitation worth stating, not a bug.

**Invalid requests:** 14/14 return Unavailable after the fix. A non-numeric O₂ used to raise a ValueError, which surfaced as HTTP 500.

**Leakage audit:**
- No session appears in both train and test (asserted in every fold).
- No fitted preprocessing: features are raw O₂ % and D0, and standardisation is used only by the eligibility checks.
- The feature rule and thresholds are fixed in advance, and the mean baseline is fitted on the same folds as OLS.
- No duplicate rows across sessions.
- One test is excluded: FLEX test 70, a confirmed source discrepancy (PSI-69 0.41 vs TP-2015-216046 0.56 mm²/s).
- Residual risk: a hardware campaign spanning consecutive days counts as separate sessions, which could make CV slightly optimistic.

## 5. Failed cases

| Case | What happened | Status |
|---|---|---|
| G20 | User alias "PMMA" removed PMMA's 9 findings | **Fixed**, with a test |
| Invalid request "O2 as text" | Server error instead of Unavailable | **Fixed**, with a test |
| Deployed check 5 (sleeping bag, local semantic on) | Abstained: "exists" counted as content, then cosine 0.347 < 0.35 | **Fixed**: generic-word list, plus the graph-named-element exception (mirrors the earlier named-investigation rule). Dev 12/12 and holdout-1 10/10 unchanged; holdout-2 unchanged |
| H2-01 | "objectives **paper**" linked to the material *Paper* → false abstention | **Not fixed.** Found on the holdout; fixing it there would be tuning on the holdout. Needs a fresh holdout after any fix |
| H2-16 to H2-20 | Literature-only facts: evidence mode returned related but non-answering findings instead of abstaining (0/5). Live Claude declined 4/5 | **Not fixed.** Evidence mode has no way to tell "related" from "answers the question"; live Claude mostly does |
| H2-06 (live) | Cited a related Apollo finding instead of the one with the number | Not fixed |
| H2-20 (live) | Off-library fact answered from a related finding | Not fixed |
| G21 | Generic gap text shown where PSI-69 data and a model exist | Minor wording issue, not fixed |
| T5 report | Default PDF has no explicit limitations section and cites NTRS sources rather than finding IDs | Not fixed; noted |
| Proposal text | Condition-gap text is generic; specificity comes from the UI context | Not fixed; noted |

## 6. Code changed by this validation

All changes are bug fixes; no threshold or feature changes.
- `backend/app/core/data.py`: alias precedence.
- `backend/app/core/models.py`: non-numeric input.
- `backend/app/core/copilot.py`: generic words and the element exception.
- New: `scripts/validate_science.py`, `scripts/check_deployed.py`, `tests/test_validation_fixes.py`, the frozen case files and locks, and `eval/validation/*`.
- Tests: 35/35 pass.

## 7. Limitations

- Every label is internal, and the system reads the same curated fields the benchmark labels come from. The gap benchmark therefore tests the logic and its wording, not the completeness of the curation.
- Sets are small (30, 23 and 5), so treat the figures as indicative.
- Nothing here amounts to independent human evaluation, certification or NASA endorsement.