# Deployed check: https://spacextinsafe.onrender.com

Run 2026-11-14T21:44:33+00:00. Passed 19/23. By kind: {'DETERMINISTIC': '15/18', 'LIVE (Claude)': '2/3', 'LIVE (Neo4j)': '1/1', 'RECORDED': '1/1'}.

| # | Check | Kind | Result | Detail |
|---|---|---|---|---|
| 1 | Backend reachable (cold start allowed) | DETERMINISTIC | PASS | healthy after 0 retries (151 ms) |
| 2 | Service status | DETERMINISTIC | PASS | Claude live=False, graph=neo4j, semantic=False |
| 3 | Neo4j retrieval verified against in-memory graph | LIVE (Neo4j) | PASS | verified=True  (152 ms) |
| 4 | Claude answer with checked citations (Saffire-II sample 2-7) | LIVE (Claude) | PASS | mode=claude model=claude-opus-5-5 cited=['EV-SAF-08'] graph=neo4j 6276 ms |
| 5 | Claude + graph: sleeping bag composition evidence | LIVE (Claude) | FAIL | mode=no-evidence model=None cited=[] graph=None 154 ms |
| 6 | Claude: conflicting evidence question | LIVE (Claude) | PASS | mode=claude model=claude-opus-5-5 cited=['EV-SAF-05', 'EV-SAF-06', 'EV-SAF-07'] graph=networkx 6708 ms |
| 7 | Custom spacecraft with a random atmosphere | DETERMINISTIC | PASS | SC-5C34A0B6 at 24.3% O2 / 73.7 kPa, 42 components screened |
| 8 | Custom material creates a library gap, not evidence | DETERMINISTIC | PASS | status='User-defined material, no evidence found', gap_created=True |
| 9 | User alias cannot remove catalogue evidence (PMMA) | DETERMINISTIC | FAIL | PMMA status after a user alias 'PMMA' was added: 'Catalogue entry, no evidence in library' |
| 10 | Supported prediction (methanol 21% O2, 2.5 mm) | DETERMINISTIC | PASS | outcome=Model-supported estimate estimate=0.5168221503173115 |
| 11 | Untested combination is not model-supported (30% O2, 1.7 mm) | DETERMINISTIC | PASS | outcome=Unavailable estimate=None |
| 12 | Out-of-range O2 refused (45%) | DETERMINISTIC | PASS | outcome=Unavailable estimate=None |
| 13 | Non-numeric input refused without a server error | DETERMINISTIC | FAIL | outcome=HTTP 500 estimate=None |
| 14 | Solid fabric refused by the droplet model | DETERMINISTIC | PASS | outcome=Unavailable estimate=None |
| 15 | Research gaps by gravity | DETERMINISTIC | PASS | PMMA partial-g: No finding in this library; SIBAL partial-g: Direct experimental evidence ['EV-LUCI-01'] |
| 16 | Interaction status and gap wording | DETERMINISTIC | FAIL | PMMA+Nomex: No documented interaction (research gap); polyester+PU: No documented interaction (research gap) |
| 17 | Dynamic PDF report changes with inputs | DETERMINISTIC | PASS | two PDFs 15431 / 16695 bytes, sha bd4651ba73ae / c0361886412d (1106 / 1591 ms) |
| 18 | Emergency instruction refused (boundary) | DETERMINISTIC | PASS | mode=boundary tier=0 boundary=True (91 ms) |
| 19 | Unsupported question abstains (Kevlar) | DETERMINISTIC | PASS | mode=no-evidence tier=0 boundary=None (253 ms) |
| 20 | Calculation answered by a tool, no LLM | DETERMINISTIC | PASS | mode=deterministic tier=0 boundary=None (61 ms) |
| 21 | Stored evaluation results served | RECORDED | PASS | stored results present; live Claude run 2026-11-14T17:35:41+00:00: 14/15 |
| 22 | Usage and cost log | DETERMINISTIC | PASS | {"requests": 6, "by_engine": {"Claude \u00b7 Advanced scientific": {"n": 2, "input_tokens": 2697, "output_tokens": 1308, "cost_usd": 0.03695, "latency_ms_median |
| 23 | Clean up test records | DETERMINISTIC | PASS | deleted 3 test records |
