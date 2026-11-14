# SpaceXtinsafe research-impact evaluation

**Status: protocol prepared; automated proxy run. No human participants have taken part, so there are no measured research times and no productivity claims.**

## 1. Automated proxy (run 15 Nov 2026)

Raw results: `backend/eval/validation/impact.json` and `.csv`. Tasks: `eval/impact_tasks.json`, hash-locked in `IMPACT.lock` before the run.

**What the proxy compares** on 5 matched tasks:
- **Traditional search proxy:** exact-keyword full-text search over the same 14 NASA publications the library was curated from.
- **SpaceXtinsafe:** the app function a researcher would use for that task.

**What it measures:**
- whether the reference pages or findings are reached
- how many pages a reader would have to open
- whether citations are verified
- machine latency

It does **not** measure human time.

| Task | Keyword search (AND) | SpaceXtinsafe |
|---|---|---|
| T1 Evidence retrieval (Nomex, microgravity) | 10 pages from 4 sources; both reference pages found, within the top 4 | 2/2 reference findings, nothing extra; 2/2 quotes verified |
| T2 Interaction (PMMA + Nomex; polyester + PU) | 6 pages; reference page **missed**. OR-search: 100 pages, reference at rank 32. Cannot show that no polyester + PU study exists | Documented interaction found (1/1); absence for polyester + PU reported with the caveat |
| T3 Applicability (cotton-fiberglass, 21% O₂, 20 cm/s) | 11 pages; 1 of 2 reference pages (results tables don't repeat material names) | 5/5 reference findings; 9 returned (precision 0.56, the 4 extras labelled partially or directly applicable); both conflicts flagged |
| T4 Gap identification (partial gravity) | 1 page (AND), 48 pages (OR); the LUCI result page not reached by either. Surfaced 7 partial-gravity pages mentioning "gap" materials (e.g. LUCI PMMA rod) | Correct gap set (5/5) and the one finding |
| T5 Report preparation (Orbital module) | Not measurable without a person | 15 kB PDF in 0.38 s, with evidence, gaps, NTRS citations and a scope disclaimer. No explicit limitations section |

The OR variant was added after the first run and is labelled post hoc in the data. Machine latencies are 0.3–6 ms per lookup, and both sides are equally fast as machines. That says nothing about human research time.

**What the proxy supports:**
- SpaceXtinsafe reaches the curated reference findings that keyword search misses when tables and results pages don't repeat the search terms (T2, T3, T4).
- It states absence explicitly, which keyword search cannot (T2, T4).
- It flags conflicts (T3).

**What the proxy does not support:**
- **Any time saving or productivity figure.**
- Completeness against the literature. The references were curated from these same publications, which favours SpaceXtinsafe by construction.
- Coverage beyond the library. Keyword search found partial-gravity PMMA material that the library lacks (T4).

## 2. Human study protocol (ready to run)

**Question.** Compared with full-text search of the same NASA publications, does SpaceXtinsafe change:
1. task completion time,
2. completeness of the evidence found, and
3. citation correctness,

for 5 types of fire-safety research task?

**Design.**
- Within-subject crossover with two matched task sets, A (the five tasks in `impact_tasks.json`) and B (parallel tasks on other materials). Freeze B before recruiting.
- Conditions:
  - **Traditional:** the 14 PDFs, a PDF reader and NTRS search.
  - **Assisted:** SpaceXtinsafe plus the PDFs.
- Counterbalance order and set assignment: AB/BA × set A/B, four arms.

**Participants.** At least 8, ideally 12 or more: engineering or science students, or researchers with no prior SpaceXtinsafe use. With n = 8 and a paired design, only large effects are detectable, so report the result as a pilot.

**Procedure.**
1. 10-minute training on each tool.
2. A cap of 20 minutes per task.
3. The participant writes an answer with citations: source and page.
4. Screen-record if participants consent.
5. Record start and stop times in the template; no self-reported times.

**Scoring.** A scorer blind to condition scores each answer against the frozen references:
- **Completeness:** share of the reference findings or pages cited.
- **Citation correctness:** share of cited pages that contain the claimed fact.
- **Absence handling:** for gap and interaction tasks, did the participant correctly state "no finding in these sources"?
- **Errors:** any claim of safety from missing evidence.

**Analysis.**
- Medians and interquartile ranges per condition, with a paired Wilcoxon test on time and completeness.
- Report every participant's data, including timeouts, as the cap time with a flag.
- No claims beyond the measured tasks.

**Ethics.** Informed consent, no personal data beyond participant code, and the right to withdraw.

**Data template.** `backend/eval/impact_human_template.csv`, one row per participant × task.

## 3. Wording for the deck

- Supported now: *"In an automated proxy on 5 matched tasks, SpaceXtinsafe reached all curated reference findings and reported absences explicitly; keyword search of the same publications missed reference pages in 3 of 4 searchable tasks. A timed user study protocol is prepared."*
- Not supported: "X× faster", "saves N hours", or any percentage productivity gain.