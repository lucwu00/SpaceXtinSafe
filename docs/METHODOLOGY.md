# Methodology

## Data
- **NASA PSI tables (CC0):** PSI-69 (FLEX, 274 droplet tests), PSI-98/99/100 (Saffire I–III), PSI-25/26 (BASS-II/BASS), PSI-68 (FLEX-2). Stored unmodified in `backend/app/data/raw/`; SHA-256 hashes in `provenance.json`.
- **42 evidence statements** from 13 NASA sources (NTRS reports, Researcher's Guide, Apollo 204 and Apollo 13 review boards, NASA History). Each keeps a verbatim quote; `scripts/verify_evidence.py` locates every quote in the source PDF text (42/42 found).
- **Materials:** 74 entries with an evidence tier (direct NASA test, related evidence, no evidence in library). User-defined materials start with no evidence; nothing is inferred for them.

## Knowledge graphs
Spacecraft graph (vehicle → compartment → object → component → material/form) and science graph (material → finding → investigation → source; tests, conditions, gaps, conflicts, models) share Material nodes. In-memory networkx is always available; when Neo4j is configured, the same graph is mirrored with idempotent `MERGE` and a sync stamp, stale nodes are deleted, and traces use parameterised Cypher.

## Retrieval
BM25 keyword, sentence-transformer (all-MiniLM-L6-v2) semantic, Reciprocal Rank Fusion hybrid, and hybrid+graph (entity linking to graph nodes, then expansion along material/investigation edges). The mode actually used is returned with every response.

## Applicability
Each finding is compared with the scenario factor by factor (material, form, gravity, O₂, pressure, flow). Factors are match / partial / mismatch / not reported; not-reported never counts as a match. Results are tiers (Directly, Partially, Contextual), never risk scores.

## FLEX burning-rate models
OLS per fuel × pressure band, nitrogen diluent only, features O₂ % and initial diameter (parameter counts include the intercept). Validated with leave-one-session-out CV against a mean baseline and a random-forest benchmark on identical folds. A model is **Model-supported** only with n ≥ 20, ≥ 8 sessions and predictive skill ≥ 0.30; otherwise **Exploratory**. Test 193F001 is excluded because the two NASA sources disagree (K 0.41 vs 0.56 mm²/s).

## Prediction eligibility
A request is checked for missing inputs, physical validity, condition compatibility (fuel, form, diluent, gravity, pressure band), the D0 domain, joint O₂–D0 support, a Delaunay hull on standardised features, kNN distance against the training 95th percentile, and local coverage (≥ 3 tests from ≥ 2 sessions). Outcome: Model-supported estimate (with 90% empirical band), Exploratory, or Unavailable, with every failed reason listed.

## Source audit
PSI-69 rows are matched to the NASA technical report Table IX by test identifier and date and classified by tolerance class: a difference within half a unit of the coarser reported precision is a rounding difference; beyond that, ≤ 5% relative is minor and > 5% substantive. Only substantive differences in model inputs or outputs (O₂, pressure, D0, K) exclude a test from fitting. Findings are then labelled Confirmed discrepancy, Potential discrepancy or Missing information. Saffire tables are checked against NTRS papers. Conflicts are shown side by side, not resolved silently.

## Evaluation protocol
Labels were written before results were inspected and locked by hash (`LABELS.lock`, `HOLDOUT.lock`, `CLAUDE_LIVE.lock`). The holdout set was never used for tuning. Totals are derived from executed results. Earlier runs are kept in `eval/` as run history.

## Multi-model routing (Scientific Copilot)
- **Tier 0, Python:** boundaries, evidence-based abstention, O₂ partial pressure, spacecraft inventory, dataset statistics, eligibility-checked FLEX predictions, navigation.
- **Tier 1, `SXS_MODEL_FAST`:** app enquiries, terminology, simple summaries.
- **Tier 2, `SXS_MODEL_STANDARD`:** evidence-grounded science.
- **Tier 3, `SXS_MODEL_DEEP`:** used when a rule-based complexity score is 3 or more. The score sums:
  - an explicit conflict question: +2;
  - a synthesis question: +2;
  - evidence from an investigation with recorded source discrepancies: +1;
  - 4 or more investigations: +1;
  - 3 or more condition variables: +1;
  - 2 or more named materials: +1.
- **Modes:** Fast caps at tier 1; Deep Research uses tier 3 for science.
- **Escalation:** the copilot moves up one tier only when the evidence passed the sufficiency checks but no claim survived the citation and number checks, or most claims failed. Missing evidence abstains before any model is called.
- **Same checks at every tier:** every tier uses the same evidence-only prompt and the same claim checks.
- **Safeguards:**
  - per-tier output-token limits;
  - a per-client rate limit;
  - a response cache;
  - a daily estimated-spend and token budget. Past the budget, the copilot falls back to evidence-retrieval mode.
- **Cost estimates:** token counts × configured prices (Anthropic pricing page, standard tier, checked 2026-11-14).
