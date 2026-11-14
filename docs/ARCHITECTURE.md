# Architecture

```mermaid
flowchart LR
  U[Browser] --> V[React + Vite on Vercel]
  V -- HTTPS /api --> R[FastAPI on Render]
  R --> S[(SQLite: spacecraft, custom materials, procedures)]
  R --> G[networkx dual graph]
  G -. idempotent MERGE sync .-> N[(Neo4j AuraDB)]
  R --> E[Retrieval: BM25 + MiniLM embeddings + RRF + graph expansion]
  R --> M[FLEX OLS models + eligibility checks]
  R --> A[Source audit]
  R --> RT{Rule-based router}
  RT -- tier 0 --> T0[Python tools: pO2, inventory, stats, FLEX models, navigation, abstention]
  RT -- tier 1 --> H[Claude Haiku]
  RT -- tier 2 --> S[Claude Sonnet]
  RT -- tier 3 --> O[Claude Opus]
  H & S & O --> CK[Same citation + number checks; escalate one tier if all claims fail]
  RT -- no key / budget / rate limit --> EV[Evidence-retrieval mode]
  R --> P[PDF report builder]
  D[(NASA PSI tables + 42 verified NTRS quotes)] --> E & M & A & G
```

- One shared scenario (spacecraft, material, form, O₂, pressure, gravity, flow, diluent, diameter) drives all modules in the frontend (`state.tsx`).
- Every save invalidates the graph cache and, when Neo4j is connected, schedules a debounced re-sync.
- Status endpoints report what actually works: semantic model loaded, Claude verified by a real call, Neo4j connected by a real sync.
