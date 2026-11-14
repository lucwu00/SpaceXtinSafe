# Requirements traceability and status matrix

Statuses: **Complete and tested** · **Implemented but not tested** · **Partially implemented** · **Blocked by external dependencies** · **Not implemented**.
"Tested" means an automated test or an executed run in this repository: `backend/tests` (29 pytest tests), `e2e/workflow.cjs` (15 UI steps), `e2e/dynamic.cjs` (14 UI steps with new, never-recorded inputs), `backend/scripts/run_eval.py`.
Live-service rows change only after they are verified on the public deployment.

| # | Requirement | Status | Evidence |
|---|---|---|---|
| P0-1 | React frontend deployed on Vercel | Implemented but not tested | `frontend/vercel.json`; awaits the user's Vercel import |
| P0-2 | FastAPI backend deployed on Render | Implemented but not tested | `backend/Dockerfile`, `render.yaml`; Docker build not run here (no Docker in the build sandbox) |
| P0-3 | Neo4j AuraDB live (idempotent MERGE sync, parameterised Cypher, multi-hop trace, failure handling, honest status) | Blocked by external dependencies | Code in `core/graph.py`; failure path tested (`test_dynamic.py::test_neo4j_failure_reported`); live sync needs AuraDB credentials in Render |
| P0-4 | Claude API live with fallback | Blocked by external dependencies | Invalid-key fallback tested; live answers need `ANTHROPIC_API_KEY` in Render |
| P0-5 | Sentence-transformer embeddings | Complete and tested | Embedding check in `eval/results.json` (42×384, unit norm, paraphrase cos 0.56 vs unrelated 0.01) |
| P0-6 | Genuine dynamic functionality (arbitrary materials, spacecraft, questions, predictions) | Complete and tested | `test_dynamic.py`, `e2e/dynamic.cjs` 14/14 |
| P0-7 | Shared state across modules | Complete and tested | Material swap propagates to screen, graph, gaps, compare, incident and report (`test_dynamic.py`) |
| P0-8 | No secrets in frontend, repo, reports or preview | Complete and tested | Keys read only from server env; `.env` ignored; snapshot builder records responses only |
| P1-1 | Material ontology with tiers; user-defined materials; object decomposition | Complete and tested | 74 materials; custom material API + UI form; decomposed objects in templates |
| P1-2 | Isometric/cutaway twin with overlays, no red/amber/green risk colours | Complete and tested | `Twin.tsx`; E2E step selects compartment and object |
| P1-3 | NASA Investigation Coverage dashboard, dataset provenance, feature map, data-usage statement | Complete and tested | `Nasa.tsx`, `/api/investigations`, `/api/datasets`, `/api/nasa-usage` |
| P1-4 | Copilot abstention (general rules, fixes C10) | Complete and tested | Dev 12/12, holdout 10/10 (deterministic evidence mode) |
| P1-5 | Live Claude evaluation, separate from deterministic evaluation | Blocked by external dependencies | `scripts/eval_claude_live.py`, 15 locked cases, `POST /api/evaluation/claude-live` (ADMIN_TOKEN); status "not run" until a key is set |
| P1-6 | Audit tolerance classes | Complete and tested | 274 FLEX rows compared; 8 confirmed, 9 potential, 6 missing-information |
| P1-7 | Holdout evaluation (not used for tuning) | Complete and tested | 22 retrieval + 10 copilot questions, `HOLDOUT.lock` |
| P1-8 | Fire Lab L1, L2 interactions with relationship and conditions, L3 as future research | Complete and tested | `FireLab.tsx`; L3 presented as requirements, not results |
| P1-9 | Gaps by dimension | Complete and tested | `/api/gaps/{dimension}` × 7 dimensions |
| P1-10 | Condition comparison with O₂ partial pressure | Complete and tested | `/api/compare/conditions`; pO₂ 19.2 kPa case in tests |
| P1-11 | Incident mission phases and procedure registry | Complete and tested | 7 phases, non-cabin types rejected with explanation, `/api/procedures` |
| P1-12 | Guided Demo Mode, 18 steps | Complete and tested | `Demo.tsx` drives the real app; manually stepped through |
| P1-13 | UX polish (focus, reduced motion, plain-language toggle) | Partially implemented | No formal accessibility audit run |
| P2-1 | Dynamic PDF reports with the required disclaimer | Complete and tested | `/api/report` includes interaction, comparison and incident from shared state |
| P2-2 | Public deployment verification | Blocked by external dependencies | Will run `e2e/dynamic.cjs` with `BASE=<public URL>` |
| P2-3 | 14-step E2E with new inputs and failure tests | Complete and tested | `e2e/dynamic.cjs` 14/14 locally |
| P2-4 | Submission materials | Complete and tested | `docs/` |
| P2-5 | Offline preview as labelled backup | Complete and tested | Static preview banner; editing needs the live backend |
| R-1 | Tier 0 deterministic processing (O₂ partial pressure, inventory, dataset statistics, FLEX predictions, navigation, boundaries, abstention) | Complete and tested | `core/router.py`, `tests/test_routing.py` |
| R-2 | Rule-based routing to Haiku / Sonnet / Opus tiers (no model used to pick a model) | Complete and tested | Routing accuracy 27/28 on locked cases (`eval/routing_cases.json`) |
| R-3 | Live Haiku, Sonnet and Opus calls with escalation | Blocked by external dependencies | Code path implemented; needs `ANTHROPIC_API_KEY` |
| R-4 | Model IDs configurable and verified against the API | Implemented but not tested | `SXS_MODEL_*`; `models.list()` check at startup and `POST /api/status/models/check` |
| R-5 | Missing evidence abstains, never escalates | Complete and tested | `test_missing_evidence_abstains_without_escalation` |
| R-6 | Copilot modes Auto / Fast / Deep Research; engine and model shown per answer | Complete and tested | Copilot drawer (screenshot-checked) |
| R-7 | Monitoring (model, reason, tokens, cost, latency, evidence, escalations, fallbacks) | Complete and tested | `GET /api/copilot/usage`, JSONL log; token and cost fields populate only on live calls |
| R-8 | Token limits, rate limit, cache, daily spending safeguard | Complete and tested | `SXS_MAXTOK_*`, `SXS_RATE_PER_MIN`, `SXS_CACHE_TTL_S`, `SXS_DAILY_BUDGET_USD`; budget fallback tested |
| R-9 | Routing evaluation of answer quality, citations, latency and cost | Blocked by external dependencies | `scripts/eval_routing.py --live --baseline` or `POST /api/evaluation/routing-live`; no cost or quality claim until run |
| — | Physical fire simulation (CFD) | Not implemented | Out of scope; listed under L3 future research |
