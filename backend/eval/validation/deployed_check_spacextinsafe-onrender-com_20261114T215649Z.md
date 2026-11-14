# Deployed check: https://spacextinsafe.onrender.com

Run 2026-11-14T21:56:49+00:00. Passed 22/23. By kind: {'DETERMINISTIC': '18/18', 'LIVE (Claude)': '2/3', 'LIVE (Neo4j)': '1/1', 'RECORDED': '1/1'}.

| # | Check | Kind | Result | Detail |
|---|---|---|---|---|
| 1 | Backend reachable (cold start allowed) | DETERMINISTIC | PASS | healthy after 0 retries (87 ms) |
| 2 | Service status | DETERMINISTIC | PASS | Claude live=True, graph=neo4j, semantic=False |
| 3 | Neo4j retrieval verified against in-memory graph | LIVE (Neo4j) | PASS | verified=True  (196 ms) |
| 4 | Claude answer with checked citations (Saffire-II sample 2-7) | LIVE (Claude) | PASS | mode=claude model=claude-opus-5-5 cited=['EV-SAF-08'] graph=neo4j 57 ms |
| 5 | Claude + graph: sleeping bag composition evidence | LIVE (Claude) | PASS | mode=claude model=claude-sonnet-5-5 cited=['EV-AP1-01', 'EV-AP1-03', 'EV-SAF-08'] graph=neo4j 52 ms |
| 6 | Claude: conflicting evidence question | LIVE (Claude) | FAIL | mode=claude model=claude-opus-5-5 cited=['EV-SAF-05', 'EV-SAF-07'] graph=networkx 67 ms |
| 7 | Custom spacecraft with a random atmosphere | DETERMINISTIC | PASS | SC-3F54560C at 25.7% O2 / 88.0 kPa, 42 components screened |
| 8 | Custom material creates a library gap, not evidence | DETERMINISTIC | PASS | status='User-defined material, no evidence found', gap_created=True |
| 9 | User alias cannot remove catalogue evidence (PMMA) | DETERMINISTIC | PASS | PMMA status after a user alias 'PMMA' was added: 'Verified NASA combustion evidence' |
| 10 | Supported prediction (methanol 21% O2, 2.5 mm) | DETERMINISTIC | PASS | outcome=Model-supported estimate estimate=0.5168221503173115 |
| 11 | Untested combination is not model-supported (30% O2, 1.7 mm) | DETERMINISTIC | PASS | outcome=Unavailable estimate=None |
| 12 | Out-of-range O2 refused (45%) | DETERMINISTIC | PASS | outcome=Unavailable estimate=None |
| 13 | Non-numeric input refused without a server error | DETERMINISTIC | PASS | outcome=Unavailable estimate=None |
| 14 | Solid fabric refused by the droplet model | DETERMINISTIC | PASS | outcome=Unavailable estimate=None |
| 15 | Research gaps by gravity | DETERMINISTIC | PASS | PMMA partial-g: No finding in this library; SIBAL partial-g: Direct experimental evidence ['EV-LUCI-01'] |
| 16 | Interaction status and gap wording | DETERMINISTIC | PASS | PMMA+Nomex: Documented interaction; polyester+PU: No documented interaction (research gap) |
| 17 | Dynamic PDF report changes with inputs | DETERMINISTIC | PASS | two PDFs 15456 / 16714 bytes, sha b617362b7746 / aecce00b24e1 (1764 / 2304 ms) |
| 18 | Emergency instruction refused (boundary) | DETERMINISTIC | PASS | mode=boundary tier=0 boundary=True (71 ms) |
| 19 | Unsupported question abstains (Kevlar) | DETERMINISTIC | PASS | mode=no-evidence tier=0 boundary=None (54 ms) |
| 20 | Calculation answered by a tool, no LLM | DETERMINISTIC | PASS | mode=deterministic tier=0 boundary=None (50 ms) |
| 21 | Stored evaluation results served | RECORDED | PASS | stored results present; live Claude run 2026-11-14T17:35:41+00:00: 14/15 |
| 22 | Usage and cost log | DETERMINISTIC | PASS | {"requests": 12, "by_engine": {"Claude \u00b7 Advanced scientific": {"n": 4, "input_tokens": 2697, "output_tokens": 1376, "cost_usd": 0.03831, "latency_ms_media |
| 23 | Clean up test records | DETERMINISTIC | PASS | deleted 3 test records |
