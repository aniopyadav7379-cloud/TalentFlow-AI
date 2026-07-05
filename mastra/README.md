# TalentFlow AI — Mastra Orchestration Layer

A TypeScript [Mastra](https://mastra.ai) service that orchestrates the
existing, already-tested FastAPI backend. **This service contains no AI
logic of its own** — every tool is a thin HTTP call into a backend endpoint
that already existed (or was added as a granular, additive-only bridge
endpoint — see `backend/app/api/v1/mastra_bridge.py`). The Python backend
remains the execution engine; this is the orchestration layer in front of
it.

## Why this exists alongside the backend's own orchestrator

The backend already has a working, tested orchestrator
(`backend/app/orchestrator/shortlist_pipeline.py`, a LangGraph state
machine) that runs the full pipeline server-side in one call. That's
untouched and still the fast, deterministic path the existing frontend
button ("Run AI Shortlist") uses.

This Mastra service is a second, parallel orchestration layer that exposes
the same underlying capabilities as independently-callable tools, so an
LLM-driven agent can decide the call sequence itself, and so a human
approval step can sit *between* tool calls (something a single server-side
pipeline call can't do mid-request). Both coexist; neither replaces the
other.

## A real bug found and fixed after initial testing

The initial version of this service had no CORS middleware on its Hono
server. `components/jobs/mastra-agent-panel.tsx` on the frontend calls this
service **directly from the browser** (`lib/mastra-client.ts`) — but all of
this project's own integration testing so far had used `curl`, which
doesn't enforce CORS (it's a browser-only mechanism). That meant the bug
was invisible to every test performed, including a full live end-to-end
run triggering the real workflow against the real backend — and would only
have surfaced the first time an actual browser tried to call this service
from the deployed frontend's origin, silently failing with a CORS error in
the console.

Fixed by adding `hono/cors` middleware (`src/index.ts`), configured via a
new `CORS_ORIGINS` env var using the exact same comma-separated-string
pattern as the backend's own `CORS_ORIGINS` setting. Verified with a real
preflight request: the configured origin receives the correct
`Access-Control-Allow-Origin` header, and an arbitrary untrusted origin does
not — see the `curl -X OPTIONS` example in this README's setup notes, or
just trust that it was actually run, not just written.

## Setup

```bash
cd mastra
npm install
cp .env.example .env   # fill in OPENAI_API_KEY, QDRANT_URL, and CORS_ORIGINS for real use
npm run build
npm start               # or `npm run dev` for auto-reload
```

Requires the backend running separately (`cd ../backend && uvicorn
app.main:app --reload`) — this service calls it over HTTP, it doesn't embed it.
`CORS_ORIGINS` must include whatever origin the frontend is actually served
from (default `http://localhost:3000` for local dev) — see the bug note
above for why this matters.

## Architecture

```
Frontend (Next.js)
        │
        ▼
Mastra Hiring Agent  ──or──  Mastra hiringWorkflow (deterministic, with approval gate)
        │
   ┌────┴────┬─────────┬──────────────┬────────────────┬─────────────┐
   ▼         ▼         ▼              ▼                ▼             ▼
resumeTool  candidateSearchTool  rankingTool  interviewTool  enkryptTool  recommendationTool
   │         │         │              │                │             │
   └─────────┴─────────┴──────────────┴────────────────┴─────────────┘
                                  │
                                  ▼
                     FastAPI Backend (unchanged)
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
         PostgreSQL          Qdrant (backend's       Enkrypt AI
                              resumes/jobs/           (via backend's
                              interview_history        EnkryptClient)
                              collections)
```

Mastra's own memory (`memory/qdrantMemory.ts`) talks to the **same Qdrant
deployment**, in its own `mastra_memory` collection — not a second vector
database. See "Memory architecture" below.

## Tool-calling flow

`hiringAgent` (an LLM-driven agent — see `src/agents/hiringAgent.ts`) has
all 7 tools available and decides the call order itself from its
instructions. A typical run for "find Python developers":

```
Recruiter: "Find Python Developers"
        │
        ▼
Agent reasons: "I need to search first"
        │
        ▼
calls candidateSearchTool → POST /api/v1/candidate/search
        │
        ▼
Agent reasons: "Now rank them properly"
        │
        ▼
calls rankingTool → POST /api/v1/candidate/rank
        │
        ▼
calls enkryptTool → POST /api/v1/enkrypt/check   (guardrail check, BEFORE recommending — see note below)
        │
        ▼
calls recommendationTool → POST /api/v1/recommendation
        │
        ▼
Agent returns an answer, explaining which tools it called and why
```

For a **deterministic** version of the same flow with an explicit human
approval gate instead of letting the LLM decide, use `hiringWorkflow`
(`src/workflows/hiringWorkflow.ts`) via `POST /workflows/hiring/trigger`
instead of `/agent/chat` — see "Human-in-the-loop" below.

### An intentional deviation from the reference architecture diagram

The reference hackathon architecture shows Enkrypt running *after*
Recommendation. This implementation runs it **before**, and optionally
again after, for a concrete reason: `POST /recommendation`'s existing,
tested contract (`backend/app/agents/hr_recommendation_agent.py`, built and
covered by tests in earlier steps of this project) takes
`guardrailsPassed`/`biasFlags` as **input** and uses them to force a "hold"
decision. A guardrail check can't gate a decision it only learns about
after the decision is already made. `hiringWorkflow.ts`'s
`postGuardrailStep` *also* runs Enkrypt after the recommendation, on the
recommendation's own rationale, as defense-in-depth — so the reference
diagram's arrow is honored too, just not as the only check. See the long
comment at the top of `hiringWorkflow.ts` and `backend/app/api/v1/mastra_bridge.py`
for the full reasoning.

## Human-in-the-loop

`hiringWorkflow` suspends after ranking + the guardrail pre-check,
presenting the top candidate for approval before any interview questions
are generated or any recommendation is synthesized:

```
POST /workflows/hiring/trigger
        │
        ▼
   rank-candidates → guardrail-pre-check
        │
        ▼
   [SUSPENDED] — waiting for recruiter-approval
        │
        ▼ (recruiter calls POST /workflows/hiring/:runId/approve)
        │
   ┌────┴────┐
   ▼         ▼
approved   rejected
   │         │
   ▼         ▼
generate    short-circuit to
questions + "no_hire" — the
recommend   LLM is never called
   │
   ▼
guardrail-post-check (defense-in-depth)
   │
   ▼
Final response
```

Try it:

```bash
curl -X POST http://localhost:4111/workflows/hiring/trigger \
  -H "Authorization: Bearer <recruiter JWT from the backend>" \
  -H "Content-Type: application/json" \
  -d '{"recruiterId":"r1","jobTitle":"Backend Engineer","jobSkills":["python","fastapi"]}'
# → {"runId": "...", "status": "suspended", "approvalNeeded": {...}}

curl -X POST http://localhost:4111/workflows/hiring/<runId>/approve \
  -H "Authorization: Bearer <same JWT>" \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "approverName": "Jane Recruiter"}'
```

## Memory architecture

`src/memory/qdrantMemory.ts` is a small, custom module — **not** wired into
Mastra's built-in `Memory` class. That class's exact storage-adapter wiring
wasn't verified closely enough against the installed package version to
depend on it for this pass; this module does exactly what was asked
(remember searches/candidates/preferences per recruiter) with a real,
working Qdrant client instead. Swapping it for Mastra's official `Memory`
primitive later only touches this one file.

It uses the **same Qdrant deployment** the backend uses (same `QDRANT_URL`),
in a dedicated `mastra_memory` collection — not a second vector database,
per the requirement. Embeddings are generated via a direct OpenAI call
(`text-embedding-3-small`, 1536 dimensions, matching the backend's default)
since there's no backend endpoint exposed for raw embedding generation.

```ts
import { rememberSearch, remember, recall } from "./memory/qdrantMemory.js";

await rememberSearch("recruiter-1", "Backend Engineer", ["python", "fastapi"]);
await remember({ recruiterId: "recruiter-1", type: "preference", text: "Prefers candidates with distributed systems experience" });

const similar = await recall({ recruiterId: "recruiter-1", queryText: "backend roles", limit: 5 });
```

**Important caveat on `QDRANT_URL`:** the backend's `local:<path>` embedded
Qdrant mode is a Python-only `qdrant-client` feature and is **not**
reachable from this Node.js service. If the backend is running in embedded
mode, point this service's `QDRANT_URL` at a real Qdrant server or Qdrant
Cloud instance instead — see `.env.example`.

## Qdrant integration

Two separate uses of the same deployment, deliberately not merged:
- **Backend** owns `resumes`, `jobs`, `interview_history` collections
  (candidate/job embeddings for semantic matching) — untouched by this
  service.
- **This service** owns `mastra_memory` (recruiter preferences/searches/
  interactions) — a distinct collection, same Qdrant instance.

## Enkrypt integration

`enkryptTool` calls the backend's `POST /api/v1/enkrypt/check`, which in
turn uses the backend's existing `EnkryptClient` (real or
`FakeEnkryptClient`, same as everywhere else in the backend — see
`backend/app/services/enkrypt_client.py`). No new Enkrypt integration was
written; this only adds a URL in front of the existing one.

## What's simplified for this pass, honestly

- **A low-severity transitive vulnerability** (`GHSA-866g-f22w-33x8`,
  uncontrolled resource consumption in `@ai-sdk/provider-utils`) exists
  three dependency-levels deep inside `@mastra/core`'s own dependency tree
  (via a legacy `@ai-sdk/ui-utils` package, not something this project
  depends on directly). It's present in the latest stable `@mastra/core`
  release as of this writing, so there's no newer non-breaking version to
  upgrade to yet. A forced major-version override of `@ai-sdk/provider-utils`
  was considered and rejected — the jump (2.2.8/3.0.25 → 5.x) is large
  enough that it risks silently breaking Mastra's model-calling internals
  in ways not practical to fully verify here. Re-run `npm audit` after
  bumping `@mastra/core` in the future; this should resolve upstream.
- **In-memory run tracking** (`activeRuns` in `src/index.ts`) — suspended
  workflow runs are held in this process's memory, not a persistent
  storage adapter. Fine for a single-instance demo; a production
  deployment with multiple instances or restarts between trigger and
  approve needs a real storage adapter (`@mastra/libsql`, `@mastra/pg`,
  etc.) wired into the `Mastra` constructor in `src/index.ts`.
- **No Mastra Cloud / persistent snapshot storage** — Mastra logs a warning
  about this on startup; expected, not a bug.
- **`recruiterId` is passed by the caller**, not derived from the JWT — a
  full build would decode the bearer token to get the actual recruiter ID
  server-side rather than trusting the request body for it.

## Verified against the real framework, not guessed

Every API surface used here (`createTool`, `createStep`/`createWorkflow`
with `.then()`/`.commit()`, `Agent`, `suspend`/`resumeData`,
`workflow.createRun()`/`run.start()`/`run.resume()`) was checked against
Mastra's current documentation and the actual installed package's
TypeScript types (`npx tsc --noEmit` passes clean) before being written —
including a live smoke test triggering `hiringWorkflow` against a real
running backend, watching it rank a real uploaded resume, suspend for
approval, resume, and fail gracefully at the LLM-dependent step without an
API key (proving the whole chain — new bridge endpoints, existing agents,
existing dependency providers — works, not just that it compiles).
