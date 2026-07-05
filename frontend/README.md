# TalentFlow AI — Frontend

## Foundation + core flow (Jobs, Candidates, AI Shortlist, Auth) ✅

Next.js 15 (App Router) · TypeScript · Tailwind v4 · Framer Motion · TanStack
Query, built directly against the tested backend API from the five backend
steps — every type in `types/` mirrors a Pydantic schema exactly, and every
call in `lib/api-client.ts` maps 1:1 onto a real, tested FastAPI route.

### What's built

| Area | What it does |
|---|---|
| **Design tokens** (`app/globals.css`) | Dark UI, indigo/purple accents, radius scale — copied directly from the Vol 3-5 handoff, not reinvented |
| **UI primitives** (`components/ui/`) | Button, Card, Badge, Input/Textarea, ScoreRing (animated circular AI-score display), EmptyState/ErrorAlert/Spinner |
| **Auth** (`app/(auth)/`, `providers/auth-provider.tsx`) | Register, login, JWT persistence, auto-redirect — a real `useAuth()` context wired to the backend, not mocked |
| **Jobs Dashboard** (`app/(dashboard)/jobs/`) | List, search/filter, create — create immediately triggers backend embedding |
| **Job Detail + AI Shortlist** (`app/(dashboard)/jobs/[jobId]/`) | The payoff screen: "Run AI Shortlist" calls the real orchestrator pipeline and renders ranked candidates with match-score rings, guardrail status, and bias flags |
| **Add Candidate** (`app/(dashboard)/candidates/`) | Create candidate + drag-and-drop PDF resume upload, shows parsed skills immediately |

### An honest scope note

The backend has no "list all candidates" endpoint (only create /
get-by-id / upload-resume) — so there's no fabricated candidate roster page
here. The Add Candidate flow is what the current API actually supports. A
`GET /candidates` list endpoint would be a small backend addition if a full
roster view becomes a priority.

### A real security fix made during this step

`next@15.1.4` (the version originally scaffolded) has a **critical CVSS
10.0 remote code execution vulnerability** (CVE-2025-66478), plus two
follow-up CVEs patched in a December 2025 security update. Caught by npm's
own install-time warning, not by chance — upgraded to `next@15.1.11`, the
fully patched version for the 15.1.x line, before writing another line of
code.

### Two real backend bugs this integration pass caught

Building the frontend against a *live* server (not just mocked fetches)
surfaced two bugs pytest's mocked fakes couldn't have caught:

1. **`CORS_ORIGINS` crashed app startup entirely.** `pydantic-settings`
   tries to JSON-decode any `List[str]`-typed env var before custom
   validators run — a plain `.env` value like
   `CORS_ORIGINS=http://localhost:3000` isn't valid JSON, so the app never
   even started. Fixed with `NoDecode` so the raw string reaches our
   validator. Now has a regression test in `test_config.py` that sets the
   real env var, not just a Python kwarg — the kwarg-only version was
   passing while the actual startup path was broken.
2. **`.env.example` shipped a truthy placeholder** (`OPENAI_API_KEY=sk-...`)
   for a secret. Since the backend README itself says `cp .env.example
   .env`, anyone following that instruction would silently get a "real key
   configured" state and break the "raises without a key" tests. Fixed to
   an empty default, with a regression test that reads `.env.example`
   directly and asserts secret placeholders stay empty.

### A real product gap this pass closed: zero-infra local dev

The backend had SQLite as a zero-infra fallback for Postgres and
`FakeEmbeddingClient` as a fallback for OpenAI — but Qdrant had no
equivalent, meaning a fresh clone genuinely couldn't run without a Qdrant
server process. Added embedded/local-file mode
(`QDRANT_URL=local:./storage/qdrant_data`, now the default) using
`qdrant-client`'s built-in embedded support — no server, no Docker, just a
local directory. `QDRANT_URL=":memory:"` and real server URLs both still
work exactly as before.

### Proven end-to-end, for real, not just in tests

With both servers running locally: registered a user, logged in, created a
job (verified real CORS preflight against `http://localhost:3000`), created
a candidate, uploaded a real generated PDF resume (parsed and embedded
correctly), and confirmed the shortlist pipeline fails **gracefully** with a
clean `503` and an actionable message when no `OPENAI_API_KEY` is
configured — proving the defense-in-depth exception handler from Step 5
actually works against a live, unmocked failure, not just a test double.

### Run it

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
npm run dev
```

Backend must be running (`cd backend && uvicorn app.main:app --reload`) —
with `OPENAI_API_KEY` set to actually exercise the AI shortlist end to end,
or without one to see the graceful degradation described above.

### Build / typecheck / lint

```bash
npm run build       # production build + full TypeScript check
npm run lint         # ESLint
```

### What's genuinely not done yet

- **No test suite for the frontend itself** (no Playwright/Vitest) — this
  pass verified correctness via a live build + a real running-server smoke
  test instead, which is a real but different bar than automated frontend
  tests. Worth adding if this becomes a longer-lived project.
- **Interviews UI** — the backend's interview-question-fetch and
  response-submission endpoints aren't wired to a screen yet (Vol4's
  Interview Dashboard / AI Interview Scorecard).
- **Analytics dashboard, live WebSocket updates, command palette** — Vol4/5
  premium features, not started.
- **No candidate roster page** — see the honest scope note above.

### Next steps

Interview screens (fetch generated questions, submit responses, show the
scored breakdown) — the natural next vertical slice, since the backend
pipeline for it is already fully built and tested.
