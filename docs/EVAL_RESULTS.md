# Evaluation results (executed 2026-11-14, `python -m scripts.run_eval`)

## Retrieval, development set (recall@5)
| Mode | All (n=38) | Single-hop (26) | Multi-hop (12) |
|---|---|---|---|
| Keyword | 0.729 | 0.974 | 0.199 |
| Semantic | 0.712 | 0.974 | 0.142 |
| Hybrid | 0.742 | 0.974 | 0.238 |
| Hybrid + graph | 0.853 | 0.974 | 0.591 |

The graph improved 10 of 12 multi-hop questions and changed none of the 26 single-hop questions. Three "unsupported" questions are scored separately.
These results come from the in-memory graph. They are **not** attributed to Neo4j, which has not yet been tested live.

## Retrieval, holdout set (recall@5, n=18 answerable of 22)
| Mode | All | Multi-hop (6) |
|---|---|---|
| Keyword | 0.571 | 0.167 |
| Semantic | 0.548 | 0.292 |
| Hybrid | 0.548 | 0.208 |
| Hybrid + graph | 0.731 | 0.589 |

On the holdout, semantic did not beat keyword overall, and the graph did not change the material (0.633) or multi-condition (0.694) categories.

## Copilot (deterministic evidence mode, no LLM)
Development 12/12 (6 answer, 3 boundary, 3 abstain). Holdout 10/10 (4 answer, 2 boundary, 4 abstain).
**Live Claude evaluation: not run** — needs `ANTHROPIC_API_KEY` on the server (15 locked cases ready).

## Prediction eligibility
10/10 cases produce the expected outcome, including an untested O₂–diameter combination that is rejected even though each value is inside its 1-D range.

## FLEX models
| Model | Status | n | Sessions | Params | Skill |
|---|---|---|---|---|---|
| Methanol 1 atm | Model-supported | 41 | 13 | 3 | 0.68 |
| Methanol 0.7 atm | Exploratory | 12 | 6 | 2 | 0.47 |
| Heptane 1 atm | Exploratory | 31 | 14 | 3 | 0.23 |
| Heptane 0.7 atm | Exploratory | 9 | 6 | 2 | 0.19 |

## Multi-model routing (`python -m scripts.eval_routing`)
Routing accuracy: **27 / 28** locked cases routed to the expected tier (tier 0: 12/12, tier 1: 4/5, tier 2: 7/7, tier 3: 4/4).
The miss is R16 ("What does blow-off mean?"), labelled tier 1. The evidence-match rule abstained instead, so it was answered at tier 0 with no claims. The rule was not changed for this result.
The labels were written by the same developer as the rules, so this measures conformity to the stated policy, not independent validity.
**Live answer quality, latency, tokens and cost per tier: not measured** (no API key). No cost saving or quality improvement is claimed.

## Software tests
29/29 pytest; UI E2E 15/15 (`workflow.cjs`) and 14/14 with new inputs (`dynamic.cjs`), run locally.
