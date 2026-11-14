# Deployed check: http://localhost:8000

Run 2026-11-14T21:20:07+00:00. Passed 19/23. By kind: {'DETERMINISTIC': '18/18', 'LIVE (Claude)': '0/3', 'LIVE (Neo4j)': '0/1', 'RECORDED': '1/1'}.

| # | Check | Kind | Result | Detail |
|---|---|---|---|---|
| 1 | Backend reachable (cold start allowed) | DETERMINISTIC | PASS | healthy after 0 retries (24 ms) |
| 2 | Service status | DETERMINISTIC | PASS | Claude live=False, graph=networkx, semantic=True |
| 3 | Neo4j retrieval verified against in-memory graph | LIVE (Neo4j) | FAIL | verified=False Neo4j not connected (1 ms) |
| 4 | Claude answer with checked citations (Saffire-II sample 2-7) | LIVE (Claude) | FAIL | mode=evidence-retrieval model=None cited=['EV-SAF-08', 'EV-SAF6-01', 'EV-SAF6-02'] graph=networkx 38 ms |
| 5 | Claude + graph: sleeping bag composition evidence | LIVE (Claude) | FAIL | mode=evidence-retrieval model=None cited=['EV-AP1-01', 'EV-AP1-03', 'EV-SAF-01'] graph=networkx 26 ms |
| 6 | Claude: conflicting evidence question | LIVE (Claude) | FAIL | mode=evidence-retrieval model=None cited=['EV-SAF-04', 'EV-SAF-05', 'EV-SAF-06'] graph=networkx 23 ms |
| 7 | Custom spacecraft with a random atmosphere | DETERMINISTIC | PASS | SC-843C3CAE at 23.3% O2 / 70.3 kPa, 42 components screened |
| 8 | Custom material creates a library gap, not evidence | DETERMINISTIC | PASS | status='User-defined material, no evidence found', gap_created=True |
| 9 | User alias cannot remove catalogue evidence (PMMA) | DETERMINISTIC | PASS | PMMA status after a user alias 'PMMA' was added: 'Verified NASA combustion evidence' |
| 10 | Supported prediction (methanol 21% O2, 2.5 mm) | DETERMINISTIC | PASS | outcome=Model-supported estimate estimate=0.5168221503173114 |
| 11 | Untested combination is not model-supported (30% O2, 1.7 mm) | DETERMINISTIC | PASS | outcome=Unavailable estimate=None |
| 12 | Out-of-range O2 refused (45%) | DETERMINISTIC | PASS | outcome=Unavailable estimate=None |
| 13 | Non-numeric input refused without a server error | DETERMINISTIC | PASS | outcome=Unavailable estimate=None |
| 14 | Solid fabric refused by the droplet model | DETERMINISTIC | PASS | outcome=Unavailable estimate=None |
| 15 | Research gaps by gravity | DETERMINISTIC | PASS | PMMA partial-g: No finding in this library; SIBAL partial-g: Direct experimental evidence ['EV-LUCI-01'] |
| 16 | Interaction status and gap wording | DETERMINISTIC | PASS | PMMA+Nomex: Documented interaction; polyester+PU: No documented interaction (research gap) |
| 17 | Dynamic PDF report changes with inputs | DETERMINISTIC | PASS | two PDFs 15448 / 16695 bytes, sha 32275d28edf0 / 1fdff2c08282 (333 / 299 ms) |
| 18 | Emergency instruction refused (boundary) | DETERMINISTIC | PASS | mode=boundary tier=0 boundary=True (2 ms) |
| 19 | Unsupported question abstains (Kevlar) | DETERMINISTIC | PASS | mode=no-evidence tier=0 boundary=None (15 ms) |
| 20 | Calculation answered by a tool, no LLM | DETERMINISTIC | PASS | mode=deterministic tier=0 boundary=None (2 ms) |
| 21 | Stored evaluation results served | RECORDED | PASS | stored results present; live Claude run 2026-11-14T17:35:41+00:00: 14/15 |
| 22 | Usage and cost log | DETERMINISTIC | PASS | {"requests": 22, "by_engine": {"Evidence retrieval (no LLM)": {"n": 10, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "latency_ms_median": 39}, "Pytho |
| 23 | Clean up test records | DETERMINISTIC | PASS | deleted 3 test records |
