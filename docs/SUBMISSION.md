# SpaceXtinSafe — From Research to Readiness
NASA Space Apps Challenge 2026 · Flame in Freefall

## Summary (short)
SpaceXtinSafe is a knowledge-driven spacecraft digital twin. It links each compartment, object and material of a configurable spacecraft to original NASA microgravity combustion data. It shows how far each finding applies to the vehicle's conditions, audits the NASA sources against each other, and gives burning-rate estimates only where the experimental data supports them.

## Description
Fire behaves differently in microgravity, and NASA's ISS and Cygnus experiments (FLEX, BASS, Saffire, SoFIE and others) produced the data to understand it. That data is spread across PSI tables, technical reports and presentations, so designers and researchers cannot easily ask "what does NASA know about the materials in this module, under these conditions?"

SpaceXtinSafe answers that question. Users:
- build or load a spacecraft;
- inspect it in a cutaway digital twin;
- trace object → component → material → finding → investigation → source across two linked knowledge graphs;
- retrieve evidence with keyword, semantic and graph-enhanced search;
- see a factor-by-factor applicability breakdown;
- explore documented material interactions;
- request FLEX droplet burning-rate estimates that are refused outside the tested domain;
- find research gaps by gravity, oxygen, pressure, airflow, form and material;
- compare configurations and atmospheres;
- replay simulated incidents across mission phases;
- export a PDF evidence report.

A Scientific Copilot answers only from retrieved evidence, and a server-side check removes uncited or unsupported numbers. An Evaluation Centre publishes executed results on locked development and holdout sets, including the cases where the graph did not help.

## NASA data used
| Dataset / source | Use |
|---|---|
| PSI-69 FLEX (274 tests) | Burning-rate models, eligibility domain, audit vs NASA TP Table IX |
| PSI-68 FLEX-2 | Test inventory, gaps |
| PSI-98/99/100 Saffire I–III | Flame-spread evidence, interactions (Saffire-II PMMA + Nomex), audit vs NTRS |
| PSI-25/26 BASS-II/BASS | Solid-fuel tests, gaps by flow and O₂ |
| NTRS reports, Researcher's Guide, Apollo 204 / Apollo 13 review boards, NASA History (Mir) | 42 findings with verbatim quotes verified against the PDFs |

See `docs/METHODOLOGY.md` for how each dataset is used, and the in-app "NASA investigations & datasets" tab for provenance.

## Results
See `docs/EVAL_RESULTS.md`. Headline: hybrid+graph retrieval reached recall@5 0.853 on the development set (multi-hop 0.591, vs 0.238 for hybrid) and 0.731 on the untouched holdout. One of four FLEX models meets the Model-supported criteria.

## Limitations
- Evidence status describes research coverage, never a flammability rating, qualification or safe/unsafe call.
- Estimates exist only for FLEX droplets (methanol and heptane, nitrogen diluent). Saffire, BASS and other data are evidence, not models.
- The library holds 42 curated findings. A gap in the library is not proof of a gap in all literature.
- Templates are illustrative, not real vehicles. Incident replays are simulated and give no instructions.
- Live Neo4j and live Claude are verified only after deployment with credentials (see `docs/STATUS_MATRIX.md`).

## Roadmap
1. Add SoFIE, ACME and Saffire IV–VI tables as they are released, and more fuels for FLEX-2.
2. Run the live Claude evaluation and publish it next to the deterministic results.
3. Add physics-based models for solids (flame spread vs flow and O₂) once enough tests exist for validation.
4. Have domain experts review the material-tier assignments and interaction relationships.
5. L3 virtual experiments: a coupled CFD-combustion interface, clearly separated from the evidence layer.

## Disclaimer
SpaceXtinSafe is an independent research and educational prototype. This report is not a certified spacecraft fire safety assessment, material qualification, operational recommendation, emergency procedure or NASA-endorsed product.
