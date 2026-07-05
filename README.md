# TalentFlow AI

An AI-powered recruitment platform: semantic candidate ranking, AI-generated
interviews, and bias-checked hiring recommendations — Qdrant for retrieval,
LangGraph for backend orchestration, Mastra for agentic orchestration,
Enkrypt AI for fairness guardrails.

```
talentflow-ai/
├── backend/    FastAPI + LangGraph + Qdrant — see backend/README.md (unchanged, execution engine)
├── frontend/   Next.js 16 — see frontend/README.md
├── mastra/     Mastra orchestration layer (TypeScript) — see mastra/README.md
└── render.yaml Render Blueprint for the backend service
```

## Local development

```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env
python scripts/init_db.py
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
cp .env.local.example .env.local
npm run dev

# Mastra orchestration layer (separate terminal, optional)
cd mastra
npm install
cp .env.example .env
npm run dev
```

Backend and frontend run with **zero external infrastructure** by default —
SQLite, embedded Qdrant, and `FakeEmbeddingClient` cover local dev. Set
`OPENAI_API_KEY` to exercise the real AI pipeline. Mastra needs a real
(non-embedded) Qdrant URL and an `OPENAI_API_KEY` for its memory module and
LLM-backed tools — see `mastra/README.md`.

## Deploying

See **TalentFlow_AI_Deployment_Guide.pdf** — frontend on Vercel, backend on
Render, database on Aiven PostgreSQL.

## Mastra orchestration layer

`mastra/` is a new, standalone TypeScript service that adds Mastra as an
agentic orchestration layer **in front of** the existing FastAPI backend.
It contains no AI logic of its own — every Mastra tool is a thin HTTP call
into a backend endpoint (existing or newly added as a granular bridge
endpoint; see `backend/app/api/v1/mastra_bridge.py`). **The FastAPI backend
remains the execution engine.** Full details, including honest
simplifications and what was verified against the real framework rather
than assumed, are in `mastra/README.md` — this section is the summary.

### Architecture

```
                   Frontend (Next.js)
                           │
                           ▼
                  Mastra Hiring Agent
                           │
          ┌────────────────┼────────────────┬───────────────┐
          │                │                │               │
          ▼                ▼                ▼               ▼
   Resume Tool    Candidate Search/Rank   Interview Tool   Enkrypt Tool
          │                │                │               │
          └────────────────┴────────────────┴───────────────┘
                           │
                           ▼
                  FastAPI Backend (unchanged)
                           │
      ┌────────────────────┼────────────────────┐
      ▼                    ▼                    ▼
  PostgreSQL           Qdrant DB          Enkrypt AI
      │                    │                    │
      └────────────────────┼────────────────────┘
                           ▼
                   Safe Hiring Decision
```

### Workflow diagram

```
Recruiter Request
     │
     ▼
Rank Candidates  (deterministic — semantic + skill-overlap, no LLM)
     │
     ▼
Guardrail Pre-Check (Enkrypt)  ── gates the recommendation, see note below
     │
     ▼
[HUMAN APPROVAL — workflow suspends here]
     │
 ┌───┴───┐
 ▼       ▼
approved  rejected → short-circuits to "no_hire", recommendation LLM never called
 │
 ▼
Generate Interview Questions
     │
     ▼
Synthesize Recommendation  (guardrailsPassed from the pre-check can force "hold")
     │
     ▼
Guardrail Post-Check (Enkrypt)  ── defense-in-depth on the recommendation's own rationale
     │
     ▼
Final Response
```

**Note on ordering:** the reference hackathon diagram shows Enkrypt after
Recommendation. This implementation runs it before (so it can gate the
decision, not just review it afterward) and optionally again after
(matching the reference diagram's arrow too, as defense-in-depth). See
`mastra/README.md` for the full reasoning — this wasn't an oversight.

### Tool-calling flow

`hiringAgent` has 7 tools available (resume upload, candidate search,
ranking, interview generate/evaluate, Enkrypt check, recommendation) and
decides the call sequence itself from its instructions:

```
Recruiter: "Find Python Developers"
   → Agent decides it needs candidate-search
   → calls candidateSearchTool → POST /api/v1/candidate/search
   → Agent decides it needs proper ranking
   → calls rankingTool → POST /api/v1/candidate/rank
   → calls enkryptTool → POST /api/v1/enkrypt/check
   → calls recommendationTool → POST /api/v1/recommendation
   → Agent returns an answer, explaining its tool-calling reasoning
```

### Memory architecture

A custom module (`mastra/src/memory/qdrantMemory.ts`), backed by the
**same Qdrant deployment** the backend already uses — a dedicated
`mastra_memory` collection, not a second vector database. Remembers, per
recruiter: previous searches, candidate interactions, and stated hiring
preferences, retrieved by semantic similarity. See `mastra/README.md` for
why this is a custom module rather than Mastra's built-in `Memory` class,
and the caveat about the backend's embedded Qdrant mode not being reachable
from Node.js.

### Qdrant integration

Backend owns `resumes`/`jobs`/`interview_history` (candidate/job matching,
untouched). Mastra owns `mastra_memory` (recruiter memory) — same Qdrant
instance, separate collection.

### Enkrypt integration

`enkryptTool` calls the backend's `POST /api/v1/enkrypt/check`, which uses
the backend's existing `EnkryptClient` — no new Enkrypt integration, just a
URL in front of the existing one.

### What changed to support this, precisely

- **Backend:** one new file (`app/api/v1/mastra_bridge.py`, 6 granular
  endpoints), one new schemas file (`app/schemas/mastra_bridge.py`), and a
  2-line addition to `app/api/v1/router.py`. Zero changes to any existing
  route file, agent, service, or model. 11 new tests; all 166 pre-existing
  tests still pass (177 total).
- **Frontend:** one new file (`lib/mastra-client.ts`), one new component
  (`components/jobs/mastra-agent-panel.tsx`), and a 2-line addition to the
  job detail page to render it. The existing "Run AI Shortlist" button and
  its data flow are completely untouched — the Mastra panel is a clearly
  labeled, separate "Run via Mastra Agent" section demonstrating the new
  orchestration layer alongside the existing one, not instead of it.
- **Everything else** (`evaluation/`, `data/`, `infra/`, Docker, the
  database schema, authentication) — not touched, because nothing about
  this integration required touching them.

## Tests

```bash
cd backend && pytest tests/ -v --cov=app
```

177 tests, including 11 for the new Mastra bridge endpoints. See
`backend/README.md` for the full breakdown of what's built, what's tested,
and honest notes on what isn't done yet.
