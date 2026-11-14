# SpaceXtinsafe: From Research to Readiness

**NASA Space Apps Challenge 2026 · Flame in Freefall**

SpaceXtinsafe is a spacecraft fire-safety *evidence* platform. It connects:

- a configurable spacecraft, made of compartments, objects, components and materials;
- original NASA microgravity combustion data (PSI) and NASA reports (NTRS).

The connection runs through two linked knowledge graphs. On top of that, the platform:

- ranks findings by how far they apply to your conditions;
- audits the NASA sources against each other;
- gives a burning-rate estimate only where the experimental data actually supports it.

> Research and education prototype. It gives no safe/unsafe verdicts, no fire-risk scores and no emergency
> instructions. It is not a certified assessment and is not NASA-endorsed.

## Modules (React frontend → FastAPI backend)

| Module | What it does | Backend |
|---|---|---|
| Design Studio | Start from a Quick Start template, customise a copy, or build from scratch. Edit atmosphere, compartments, objects and components; changes are validated and saved in SQLite. | `/api/spacecraft`, `/api/templates` |
| Digital twin | Interactive compartment map. Select a compartment, then an object; see its components, their materials and evidence status. | `/api/spacecraft/{id}/screen` |
| Material inventory | Every component with its evidence status, plus the material library with finding counts. | same |
| Knowledge graphs | Force-directed explorer of the spacecraft graph and the science graph. They are linked through shared Material nodes. Shows multi-hop traces (object → component → material → finding → investigation → source). Neo4j sync button. | `/api/graph/*`, `/api/status/neo4j/sync` |
| Mission Workspace | Free-text question plus conditions. Shows retrieved evidence, a factor-by-factor applicability ranking, Fire Safety Insights and an eligibility-checked prediction. | `/api/search`, `/api/evidence/rank`, `/api/insights`, `/api/predict` |
| Evidence library | Search all 42 verified findings in keyword, semantic, hybrid, hybrid+graph or keyword+graph mode, with filters. | `/api/search` |
| Virtual Fire Lab | L1 material, component or question profile with tiered evidence and NTRS literature search; L2 documented material interactions (relationship and test conditions); FLEX droplet models with 90% bands; L3 future-simulation requirements (no results claimed). | `/api/materials/{id}`, `/api/interactions`, `/api/models`, `/api/literature` |
| Research gaps | Gaps by dimension: gravity, oxygen, pressure, airflow, form, material pairs, compartment. | `/api/gaps`, `/api/gaps/{dimension}` |
| Compare scenarios | 2–3 configurations side by side, or one material under two atmospheres (with O₂ partial pressure). | `/api/compare`, `/api/compare/conditions` |
| Evidence audit | Side-by-side source values, normalisation, citations, affected findings, modelling decisions and open questions. Downloadable as CSV or JSON. | `/api/audit`, `/api/audit.csv` |
| Incident intelligence | Simulated replay across 7 mission phases: resolves the compartment, lists unconfirmed candidate components, retrieves evidence and historical analogues, and refers to a registry of authorised procedures without giving instructions. | `/api/incidents/*`, `/api/procedures` |
| Scientific Copilot | Global drawer with Auto / Fast / Deep Research modes. Rule-based routing sends each question to Python tools (no LLM), Haiku, Sonnet or Opus. It shows the engine, model, reason, tokens, estimated cost and latency. Claims that fail the citation or number checks are removed at every tier. Boundary questions are refused, and missing evidence abstains. | `/api/copilot`, `/api/copilot/usage` |
| AI Evaluation Centre | Retrieval by mode (single-hop and multi-hop), effect of the graph on each question, copilot cases, eligibility cases, model cards, run history. | `/api/evaluation` |
| Mission reports | Dynamic PDF built from the current configuration, scenario, prediction, interaction, comparison and incident, with methodology, sources, AI disclosure and the required disclaimer. | `/api/report` |
| NASA coverage | Investigation coverage dashboard, investigation → feature map, dataset provenance and a NASA data-usage statement. | `/api/investigations`, `/api/datasets`, `/api/nasa-usage` |
| Guided demo | 18 steps that drive the real app (header button). | — |

All modules share one spacecraft selection (header) and one scenario: material, form, O₂, pressure, gravity, flow, diluent and droplet diameter.

## Data (all original public NASA files)

**NASA PSI experimental tables (CC0)**

| Table | Contents |
|---|---|
| PSI-69 | FLEX, 274 droplet tests |
| PSI-98 | Saffire-I |
| PSI-99 | Saffire-II |
| PSI-100 | Saffire-III |
| PSI-25 | BASS-II, 129 tests |
| PSI-26 | BASS |
| PSI-68 | FLEX-2 |

These tables are in `backend/app/data/raw/`. Their SHA-256 hashes match the acquisition manifest (`provenance.json`).

**42 evidence statements**

- They come from 13 sources: NTRS reports, the Researcher's Guide, the Apollo 204 and Apollo 13 review board reports, and the NASA History article on Mir.
- Every statement keeps a verbatim quote.
- `scripts/verify_evidence.py` finds each quote in the source PDF text and records its page. Any quote it cannot find is rejected; all 42 passed.

**Derived files**

- `flex_tp_table9.json`: all 276 rows of NASA/TP-2015-216046 Table IX, parsed by `scripts/parse_flex_table9.py`.
- `saffire_ntrs_table1.json`: 13 rows, each matched verbatim against PDF p.30.

**Spacecraft templates** are generic and illustrative. They do not represent real vehicles.

## Science engine

**FLEX burning-rate models**

- Ordinary least squares (OLS) with an intercept, one model per fuel × pressure band. Nitrogen diluent only.
- Validated by leave-one-session-out cross-validation. A random forest and a mean baseline are run on identical folds.
- Parameter counts include the intercept.
- The PSI header "Burning rate; mm" is the burning-rate constant in mm²/s. This is verified against the TP Table IX header and its column definition.

**Prediction eligibility**

| Outcome | When |
|---|---|
| Unavailable | Required inputs are missing; inputs are physically invalid; experimental conditions differ (form, fuel, diluent, gravity); no pressure band matches; the point is outside the convex hull *and* far from tested points; or the droplet diameter is out of range *and* not jointly covered. |
| Exploratory | The model is exploratory, the point is outside the hull but close to tested points, the point is inside the hull but nearest-neighbour distance is above the training 95th percentile, or local coverage is too sparse. |
| Model-supported | All checks pass. |

The checks are:

- **Joint support:** convex-hull membership (Delaunay, standardised features), plus the normalised distance to the 3 nearest neighbours compared with the training 95th percentile, plus local coverage (at least 3 tests from at least 2 sessions).
- **Diameter for models without it as a predictor:** for models that do not use droplet diameter, the diameter is still checked against the joint O₂ and diameter domain.

**Audit**

- All 274 PSI-69 rows are matched to Table IX by FLEX identifier and date, across 11 fields.
- The Saffire PSI tables are compared with NTRS Table 1.

| Status | Count |
|---|---|
| Confirmed discrepancy | 8 |
| Potential discrepancy | 9 |
| Missing information | 6 |

Main findings:

- **FLEX test 193F001:** K = 0.41 in PSI vs 0.56 mm²/s in TP. Diameter, extinction diameter and burn time also differ. The test is excluded from fitting.
- **Burning-rate unit label:** "mm" in PSI vs "mm²/s" in TP.
- **Saffire-II sample 2-6 flow:** 20 vs 25 cm/s.
- **Saffire-III flow:** 30 vs 25 cm/s.
- **Saffire-I thickness:** a cm column header vs 0.37 mm.
- **Saffire-III thickness:** 0.33 cm vs 0.37 mm.
- **Saffire-II thickness:** "037 mm" lacks a decimal point.
- **Saffire-II samples 2-6 and 2-9:** material is blank.
- **Numbering:** test numbers differ between PSI and TP for 120 rows. The rows were matched by identifier, so this has no effect on values.

## Evaluation (actual results, `backend/eval/results.json`)

Labels were written before the first run. Their hashes are locked in `eval/LABELS.lock`. The set has 26 single-hop questions, 12 multi-hop questions and 3 unsupported ones; recall@5 and MRR are reported below.

| Mode | All recall@5 | Single-hop recall@5 | Multi-hop recall@5 | Multi-hop MRR |
|---|---|---|---|---|
| keyword (BM25) | 0.729 | 0.974 | 0.199 | 0.357 |
| semantic (all-MiniLM-L6-v2, 384-d, embeddings verified) | 0.712 | 0.974 | 0.142 | 0.264 |
| hybrid (RRF) | 0.742 | 0.974 | 0.238 | 0.350 |
| hybrid + graph | **0.853** | 0.974 | **0.591** | **0.688** |

**Where the graph helped:** compared question by question with hybrid, it made no difference on any of the 26 single-hop questions. On the 12 multi-hop questions it improved 10 and left 2 unchanged.

**Run history:** run 1 found a bug in entity linking. When no spacecraft was named, only one spacecraft was searched. After the fix, multi-hop recall rose from 0.411 to 0.591. The labels were not changed.

**Disclosure:** the multi-hop questions name spacecraft elements defined in this app's own templates.

**Copilot (deterministic evidence mode):** development 12/12 (answer 6/6, boundary 3/3, abstain 3/3); holdout 10/10. The earlier C10 failure (aerogel) was fixed with general abstention rules, not a case-specific patch.
**Live Claude:** a separate 15-case evaluation (`scripts/eval_claude_live.py`, locked by `CLAUDE_LIVE.lock`) is **not run yet**: it needs an API key on the server.

**Holdout (22 questions, never used for tuning):** hybrid+graph recall@5 0.731 vs keyword 0.571, semantic 0.548, hybrid 0.548. See `docs/EVAL_RESULTS.md`.

**Eligibility:** 10 of 10 cases behaved as specified.

**Models:**

| Model | Status | n / sessions | Params | OLS MAE | RF MAE | Baseline MAE | Skill |
|---|---|---|---|---|---|---|---|
| FLEX-K-METH-1atm | Model-supported | 41 / 13 | 3 | 0.031 | 0.047 | 0.097 | 0.68 |
| FLEX-K-METH-0.7atm | Exploratory (few tests) | 12 / 6 | 2 | 0.054 | 0.092 | 0.102 | 0.47 |
| FLEX-K-HEPT-1atm | Exploratory (skill 0.23 < 0.30) | 31 / 14 | 3 | 0.106 | 0.145 | 0.137 | 0.23 |
| FLEX-K-HEPT-0.7atm | Exploratory | 9 / 6 | 2 | 0.110 | 0.130 | 0.135 | 0.19 |

OLS is kept as the primary model because the random forest never achieved a lower out-of-fold MAE.

## Run locally

```bash
cd backend && pip install -r requirements.txt && cp .env.example .env    # export the variables, or use your process manager
python -m pytest -q                         # 29 tests
python -m scripts.eval_routing              # routing accuracy (add --live --baseline with a key)
python -m scripts.run_eval                  # regenerates eval/results.json
uvicorn app.main:app --port 8000            # API at http://localhost:8000/docs
cd ../frontend && npm install && npm run dev  # UI at http://localhost:5173 (proxies /api to :8000)
# or: npm run build, after which the backend serves the UI at http://localhost:8000
node ../e2e/workflow.cjs                    # 15-step UI check (Playwright + Chromium)
node ../e2e/dynamic.cjs                     # 14 steps with new inputs and failure checks
```

## Configuration

| Variable | Purpose | Without it |
|---|---|---|
| `ANTHROPIC_API_KEY` (server only) | Claude writes the copilot answers, and each claim is checked. | Evidence-retrieval answers, labelled "Claude: off". |
| `ANTHROPIC_MODEL` | Default `claude-sonnet-5-5`. | — |
| `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` | Mirrors the graph to Neo4j AuraDB at startup and after every configuration save (debounced), or on "Sync to Neo4j". Shows "connected" only after a real sync succeeds. | In-memory graph + SQLite, labelled as such. |
| `SPACEXI_SEMANTIC` | `1` loads the sentence-transformer. `0` disables it. | `auto` search uses keyword + graph and says so. |
| `ALLOWED_ORIGINS` | CORS, needed if the frontend is hosted separately. | `*` |
| `ADMIN_TOKEN` | Protects `POST /api/evaluation/claude-live` and `POST /api/evaluation/routing-live` (header `X-Admin-Token`). | Endpoints disabled. |
| `SXS_MODEL_FAST` / `_STANDARD` / `_DEEP` | Copilot tier models (default `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`), verified against the API at startup. | — |
| `SXS_MAXTOK_*`, `SXS_RATE_PER_MIN`, `SXS_CACHE_TTL_S`, `SXS_DAILY_BUDGET_USD`, `SXS_DAILY_TOKEN_BUDGET`, `SXS_PRICE_*` | Token limits, rate limit, cache, spending safeguard, prices for estimates. | Defaults in `.env.example`. |
| `VITE_API_BASE_URL` (frontend build) | API origin, if separate. | Same-origin. |

**Neo4j AuraDB:**

1. Create a free instance at console.neo4j.io.
2. Copy the connection URI (`neo4j+s://…`), the username and the password into the environment.
3. Restart the backend.
4. Open **Knowledge graphs** and press **Sync to Neo4j**.

Nodes are written with the label `:SXS`. Each sync replaces them.

**Claude:**

1. Create a key at console.anthropic.com.
2. Set `ANTHROPIC_API_KEY` on the server, never in the frontend.
3. The header pill changes to "live (verified)" after the first successful call.

**Semantic model:**

- The model downloads from Hugging Face on first start.
- The Dockerfile pre-downloads it into the image.
- Plan for roughly 1–2 GB of RAM with torch loaded (not measured here).

## Public deployment

Primary: React on **Vercel** (`frontend/vercel.json`, set `VITE_API_BASE_URL`) and FastAPI on **Render** (`render.yaml`, `backend/Dockerfile`), with Neo4j AuraDB and Claude configured by Render secrets. Step by step: `docs/DEPLOY.md`.
Alternative: `Dockerfile.single-service` serves the built UI from FastAPI on one port (for example, on Hugging Face Spaces).

Then run `BASE=https://<your-url> node e2e/dynamic.cjs` against the public URL.

## Documentation

`docs/`: SUBMISSION (summary, description, NASA data, limitations, roadmap), METHODOLOGY, ARCHITECTURE (diagram), EVAL_RESULTS, AI_DISCLOSURE, STATUS_MATRIX (requirements traceability), DEPLOY, DEMO.

## Not done / limitations

- **Deployment not tested here:** the Docker image was not built in this environment (no Docker available), and no public deployment was made from this session. That needs your hosting account.
- **Claude not tested live:** the Claude copilot path was not exercised against the live API, because no key was set.
- **Neo4j not tested live:** the Neo4j sync was not exercised against a live AuraDB instance.
- **Small evidence library:** 42 curated statements, not all NASA literature. Gap counts are relative to this library.
- **Limited models:** the only quantitative models are the FLEX droplet models. Fabric spread rates are shown as observations; there are too few independent tests to fit a model.
- **Same author for system and labels:** the evaluation labels were written by the same assistant that built the system. Treat the results as indicative.
