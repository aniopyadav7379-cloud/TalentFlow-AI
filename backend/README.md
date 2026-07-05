# TalentFlow AI — Backend

## Step 1: Foundation Layer ✅
## Step 2: Embedding Pipeline (resume + job ingestion) ✅
## Step 3: The Agent Swarm ✅
## Step 4: Evaluation Layer + Orchestrator ✅
## Step 5: FastAPI Layer + Interview Scoring Pipeline ✅

**157 tests passing, 92% coverage.** The backend is now a complete,
runnable, testable product: register a user, create a job, upload resumes,
run the shortlist pipeline, fetch AI-generated interview questions, submit
responses, get a guardrail-checked recommendation — all over real HTTP,
proven by `test_full_recruitment_flow_end_to_end`.

### What's in Step 5

| File | Purpose |
|---|---|
| `app/core/security.py` | Password hashing (bcrypt, direct — see note below) + JWT issue/verify |
| `app/api/deps.py` | Every dependency the routes need (db, vector store, LLM/embedding/Enkrypt clients, current-user auth) — this is what makes `dependency_overrides` work cleanly in tests |
| `app/api/v1/auth.py` | Register, login, `/me` |
| `app/api/v1/jobs.py` | Job CRUD; create/update automatically (re-)embeds via `JobIngestionService` |
| `app/api/v1/candidates.py` | Candidate CRUD + PDF resume upload (content-type + 10MB size guards) |
| `app/api/v1/applications.py` | `POST /jobs/{id}/shortlist` — runs the Step 4 orchestrator over HTTP; list/get applications |
| `app/api/v1/interviews.py` | Fetch generated questions; submit responses (triggers the new pipeline below) |
| `app/orchestrator/interview_evaluation_pipeline.py` | **New second orchestrator** — scores real interview responses, re-runs guardrails + HR recommendation with actual interview data |
| `app/main.py` | App wiring, CORS, defense-in-depth exception handlers for uncaught provider failures |
| `tests/conftest.py`'s `client` fixture | Full `TestClient` with every external dependency swapped for a deterministic fake — real routes, real auth, real validation |

### The interview evaluation pipeline (the piece that closes the loop)

`ShortlistPipeline` (Step 4) generates interview questions but can't score
answers that don't exist yet — a human has to actually conduct the
interview. `InterviewEvaluationPipeline` picks up from there:

```
score_responses → persist InterviewResponse rows → re-synthesize HR recommendation
                → post-hoc fairness/grounding check on the NEW rationale
                → same hard override: guardrail failure forces "hold" in code
```

It deliberately does **not** auto-advance `Application.status` to
offered/rejected — that's a consequential human decision. It sets status to
`INTERVIEWING` (a factual statement: the interview happened) and leaves
hire/reject to a recruiter.

Two safety properties are tested directly, not assumed:
- **Fails closed with no prior evaluation** — if the Step 4 guardrail check
  never ran or its record can't be found, the pipeline treats the candidate
  as *not cleared*, not as a pass-by-default.
- **Prior bias flags carry forward** — a flag raised during resume analysis
  doesn't get silently dropped just because the interview stage's own
  checks pass cleanly.

### An honest bcrypt/passlib note

`passlib` (the usual FastAPI-tutorial choice for password hashing) is
unmaintained and its 1.7.4 release has a confirmed, unresolved
incompatibility with `bcrypt` 4.x/5.x's stricter internal validation — it
throws `ValueError: password cannot be longer than 72 bytes` during its own
internal self-test, before your code even runs. Rather than pin to an old
`bcrypt` to route around an unmaintained dependency, `security.py` calls
`bcrypt` directly. Simpler, and doesn't depend on a package with open,
unaddressed compatibility issues for something security-critical.

### Try it for real

```bash
cd backend
pip install -r requirements.txt --break-system-packages
cp .env.example .env
uvicorn app.main:app --reload
```

Then visit `http://localhost:8000/docs` for interactive Swagger UI. Without
`OPENAI_API_KEY`/`ENKRYPT_API_KEY` set, embedding falls back to
`FakeEmbeddingClient` automatically — but `get_llm_client()`/
`get_enkrypt_client()` will raise without real credentials (Step 3/4's
intentional "never silently fake a real recommendation" design). Set
`OPENAI_API_KEY` to actually exercise the full pipeline by hand.

### Run the tests

```bash
pytest tests/ -v --cov=app --cov-report=term-missing
```

### What's genuinely not done yet

- **Enkrypt's real API contract** is still unverified (flagged since Step
  4) — `enkrypt_client.py`'s endpoint paths are best-effort.
- **No rate limiting, no pagination cursors** (offset/limit only), **no
  WebSocket live updates** (the Vol 4 design doc calls for these — not
  built here, this step is REST-only).
- **The frontend.** This is the natural stopping point before it: the API
  contract (every Pydantic schema, every route, every status code) is now
  stable and tested. Building UI against it won't require backend rework.

### Next steps

Frontend — Next.js per the Vol 3-5 design handoff, built against this exact
API. Say the word when you're ready to start on it.




