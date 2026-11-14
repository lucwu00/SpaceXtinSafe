# Deployment (Vercel + Render + Neo4j AuraDB + Claude)

1. **Neo4j AuraDB:** create a free instance and keep the URI (`neo4j+s://…`), the username and the password.
2. **Render (backend):** New → Blueprint → select this repo (`render.yaml`). In the dashboard, set the secrets:
   - `ANTHROPIC_API_KEY`
   - `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
   - `ALLOWED_ORIGINS` (your Vercel URL)
   - `ADMIN_TOKEN` (a random string)

   The *standard* plan (2 GB) fits the semantic model. On smaller plans, set `SPACEXI_SEMANTIC=0`; the UI then reports keyword + graph retrieval.
   SQLite on Render is ephemeral, so user-made spacecraft reset on redeploy. Add a Render disk mounted at `/app/data` to keep them.
3. **Vercel (frontend):** import the repo with root directory `frontend`. Set `VITE_API_BASE_URL=https://<render-service>.onrender.com`, then deploy.
4. **Verify:**
   - `GET /api/status` should show `semantic.loaded`, `graph.connected` and, after a Copilot question, `copilot.verified_live`.
   - `POST /api/status/neo4j/sync` re-syncs the graph.
   - `curl -X POST -H "X-Admin-Token: $ADMIN_TOKEN" https://<api>/api/evaluation/claude-live` runs the live Claude evaluation.
   - `curl -X POST -H "X-Admin-Token: $ADMIN_TOKEN" "https://<api>/api/evaluation/routing-live?baseline=true"` runs the routing evaluation with real Haiku, Sonnet and Opus calls, plus an always-Opus baseline. This costs a little credit.
   - `POST /api/status/models/check` confirms that the three model IDs exist for your key.
   - `BASE=https://<vercel-url> node e2e/dynamic.cjs` runs the UI test against the public site.

Single-service alternative: `Dockerfile.single-service` builds the frontend and serves it from FastAPI (for example, on Hugging Face Spaces).
