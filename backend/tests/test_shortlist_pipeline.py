import pytest

from app.db.postgres.models import (
    Application,
    ApplicationStatus,
    Candidate,
    Evaluation,
    Interview,
    InterviewStatus,
    Job,
    JobStatus,
    User,
    UserRole,
)
from app.orchestrator.shortlist_pipeline import PipelineFatalError, ShortlistPipeline
from app.schemas.evaluation import FairnessCheckResult
from app.services.enkrypt_client import EnkryptError, FakeEnkryptClient
from app.services.job_ingestion import JobIngestionService
from app.services.llm_client import FakeLLMClient
from app.services.resume_ingestion import ResumeIngestionService
from tests.pdf_helpers import make_pdf_bytes

VALID_ANALYSIS = {
    "summary": "Backend engineer with strong Python and API design experience.",
    "seniority_level": "mid",
    "strengths": ["Strong Python and FastAPI experience"],
    "weaknesses": ["No leadership experience mentioned"],
    "red_flags": [],
}

VALID_QUESTIONS = {
    "questions": [
        {"id": "q1", "question": "Explain how you would design a rate limiter.", "category": "system_design"},
        {"id": "q2", "question": "Describe a challenging bug you fixed.", "category": "technical"},
    ]
}

STRONG_HIRE = {
    "decision": "strong_hire",
    "summary": "Excellent candidate — strong technical fit.",
    "rationale": "High match score driven by direct skill overlap with the role's requirements.",
}


def _router_responder(system_prompt: str, user_prompt: str) -> dict:
    """Routes a single shared FakeLLMClient to the right canned response based on which agent is calling."""
    if "analyzing a resume" in system_prompt:
        return VALID_ANALYSIS
    if "designing role-specific interview" in system_prompt:
        return VALID_QUESTIONS
    if "final hiring recommendation" in system_prompt:
        return STRONG_HIRE
    raise AssertionError(f"Unexpected system prompt reached the test router: {system_prompt[:80]}")


@pytest.fixture()
def recruiter(db_session) -> User:
    user = User(email="recruiter@talentflow.ai", hashed_password="x", full_name="Recruiter", role=UserRole.RECRUITER)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def open_job(db_session, recruiter) -> Job:
    job = Job(
        title="Backend Engineer",
        description="Build and scale REST APIs using Python and FastAPI.",
        skills=["python", "fastapi", "postgresql"],
        status=JobStatus.OPEN,
        created_by_id=recruiter.id,
    )
    db_session.add(job)
    db_session.commit()
    return job


def _ingest_candidate_resume(db_session, vector_store, embedding_client, local_storage, name, email, resume_text):
    candidate = Candidate(full_name=name, email=email)
    db_session.add(candidate)
    db_session.commit()
    service = ResumeIngestionService(db_session, vector_store, embedding_client, local_storage)
    resume = service.ingest(candidate.id, f"{email}.pdf", make_pdf_bytes(resume_text))
    return candidate, resume


def test_pipeline_produces_ranked_shortlist(db_session, vector_store, embedding_client, local_storage, open_job):
    strong_candidate, strong_resume = _ingest_candidate_resume(
        db_session, vector_store, embedding_client, local_storage,
        "Asha Kumar", "asha@example.com",
        "Skills: python, fastapi, postgresql\n5 years of experience building backend APIs.",
    )
    weak_candidate, weak_resume = _ingest_candidate_resume(
        db_session, vector_store, embedding_client, local_storage,
        "Ravi Sharma", "ravi@example.com",
        "Skills: photoshop, illustrator\n3 years of experience in graphic design.",
    )
    JobIngestionService(db_session, vector_store, embedding_client).ingest(open_job)

    llm_client = FakeLLMClient(responder=_router_responder)
    enkrypt_client = FakeEnkryptClient()
    pipeline = ShortlistPipeline(db_session, vector_store, embedding_client, llm_client, enkrypt_client)

    final_state = pipeline.run(open_job.id, top_k=5)
    shortlist = final_state["shortlist"]

    assert len(shortlist) == 2
    assert shortlist[0].candidate_id == strong_candidate.id
    assert shortlist[0].match_score > shortlist[1].match_score
    assert shortlist[0].passed_guardrails is True
    assert "python" in [s.lower() for s in shortlist[0].top_skills]
    assert final_state["errors"] == []


def test_pipeline_persists_application_evaluation_and_interview_rows(
    db_session, vector_store, embedding_client, local_storage, open_job
):
    candidate, resume = _ingest_candidate_resume(
        db_session, vector_store, embedding_client, local_storage,
        "Asha Kumar", "asha@example.com",
        "Skills: python, fastapi, postgresql\n5 years of backend experience.",
    )
    JobIngestionService(db_session, vector_store, embedding_client).ingest(open_job)

    llm_client = FakeLLMClient(responder=_router_responder)
    pipeline = ShortlistPipeline(db_session, vector_store, embedding_client, llm_client, FakeEnkryptClient())
    final_state = pipeline.run(open_job.id)
    entry = final_state["shortlist"][0]

    application = db_session.get(Application, entry.application_id)
    assert application is not None
    assert application.status == ApplicationStatus.SHORTLISTED
    assert application.candidate_id == candidate.id
    assert application.match_score == entry.match_score

    evaluation = db_session.query(Evaluation).filter_by(application_id=application.id).one()
    assert evaluation.passed_guardrails is True

    interview = db_session.query(Interview).filter_by(application_id=application.id).one()
    assert interview.status == InterviewStatus.PENDING
    assert len(interview.questions) == 2
    assert interview.questions[0]["category"] == "system_design"


def test_pipeline_guardrail_failure_flows_through_to_shortlist_entry(
    db_session, vector_store, embedding_client, local_storage, open_job
):
    _ingest_candidate_resume(
        db_session, vector_store, embedding_client, local_storage,
        "Asha Kumar", "asha@example.com",
        "Skills: python, fastapi\n4 years of experience.",
    )
    JobIngestionService(db_session, vector_store, embedding_client).ingest(open_job)

    def failing_fairness(text, context):
        return FairnessCheckResult(fairness_score=0.2, bias_flags=["age_coded_language"], passed=False)

    llm_client = FakeLLMClient(responder=_router_responder)
    enkrypt_client = FakeEnkryptClient(fairness_responder=failing_fairness)
    pipeline = ShortlistPipeline(db_session, vector_store, embedding_client, llm_client, enkrypt_client)

    final_state = pipeline.run(open_job.id)
    entry = final_state["shortlist"][0]

    assert entry.passed_guardrails is False
    assert "age_coded_language" in entry.bias_flags
    # The HR agent's hard override must have forced "hold" language into the summary,
    # regardless of what the (router-fixed) LLM said.
    assert "Held for human review" in entry.recommendation


def test_pipeline_skips_candidate_with_out_of_sync_resume_without_crashing(
    db_session, vector_store, embedding_client, open_job
):
    """
    Simulates Qdrant/Postgres drift: a vector exists in Qdrant pointing at a
    resume_id that either doesn't exist in Postgres, or exists but never
    finished parsing. The pipeline must record this as a per-candidate error
    and continue, not crash the whole run.
    """
    JobIngestionService(db_session, vector_store, embedding_client).ingest(open_job)
    orphan_vector = embedding_client.embed_one("Skills: python, fastapi\nSome resume text.")
    vector_store.upsert_resume("orphan-resume-id", "orphan-candidate-id", orphan_vector, {"skills": ["python", "fastapi"]})

    llm_client = FakeLLMClient(responder=_router_responder)
    pipeline = ShortlistPipeline(db_session, vector_store, embedding_client, llm_client, FakeEnkryptClient())

    final_state = pipeline.run(open_job.id)

    assert final_state["shortlist"] == []
    assert len(final_state["errors"]) == 1
    assert final_state["errors"][0]["stage"] == "analyze_resumes"


def test_pipeline_raises_fatal_error_for_unknown_job(db_session, vector_store, embedding_client):
    llm_client = FakeLLMClient(responder=_router_responder)
    pipeline = ShortlistPipeline(db_session, vector_store, embedding_client, llm_client, FakeEnkryptClient())
    with pytest.raises(PipelineFatalError):
        pipeline.run("nonexistent-job-id")


def test_pipeline_rerun_is_idempotent_no_duplicate_applications(
    db_session, vector_store, embedding_client, local_storage, open_job
):
    _ingest_candidate_resume(
        db_session, vector_store, embedding_client, local_storage,
        "Asha Kumar", "asha@example.com",
        "Skills: python, fastapi\n4 years of experience.",
    )
    JobIngestionService(db_session, vector_store, embedding_client).ingest(open_job)

    llm_client = FakeLLMClient(responder=_router_responder)
    pipeline = ShortlistPipeline(db_session, vector_store, embedding_client, llm_client, FakeEnkryptClient())

    pipeline.run(open_job.id)
    pipeline.run(open_job.id)  # re-run for the same job

    applications = db_session.query(Application).filter_by(job_id=open_job.id).all()
    evaluations = db_session.query(Evaluation).all()
    assert len(applications) == 1
    assert len(evaluations) == 1


def test_pipeline_records_error_when_resume_analysis_llm_call_fails(
    db_session, vector_store, embedding_client, local_storage, open_job
):
    """If ResumeAnalysisAgent raises AgentError for one candidate, the pipeline
    must record it and continue — not crash, and not produce a shortlist entry
    for that candidate."""
    _ingest_candidate_resume(
        db_session, vector_store, embedding_client, local_storage,
        "Asha Kumar", "asha@example.com",
        "Skills: python, fastapi\n4 years of experience.",
    )
    JobIngestionService(db_session, vector_store, embedding_client).ingest(open_job)

    def failing_responder(system_prompt, user_prompt):
        if "analyzing a resume" in system_prompt:
            return {"summary": "too short"}  # missing required fields -> ValidationError -> AgentError
        return _router_responder(system_prompt, user_prompt)

    llm_client = FakeLLMClient(responder=failing_responder)
    pipeline = ShortlistPipeline(db_session, vector_store, embedding_client, llm_client, FakeEnkryptClient())

    final_state = pipeline.run(open_job.id)

    assert final_state["shortlist"] == []
    assert any(e["stage"] == "analyze_resumes" for e in final_state["errors"])


def test_pipeline_records_error_when_guardrail_check_fails(
    db_session, vector_store, embedding_client, local_storage, open_job
):
    _ingest_candidate_resume(
        db_session, vector_store, embedding_client, local_storage,
        "Asha Kumar", "asha@example.com",
        "Skills: python, fastapi\n4 years of experience.",
    )
    JobIngestionService(db_session, vector_store, embedding_client).ingest(open_job)

    def broken_fairness(text, context):
        raise EnkryptError("Enkrypt service temporarily unavailable")

    llm_client = FakeLLMClient(responder=_router_responder)
    enkrypt_client = FakeEnkryptClient(fairness_responder=broken_fairness)
    pipeline = ShortlistPipeline(db_session, vector_store, embedding_client, llm_client, enkrypt_client)

    final_state = pipeline.run(open_job.id)

    # No guardrail report -> synthesize_recommendations still runs, but fails
    # closed (guardrails_passed=False), so the candidate still reaches the
    # shortlist — just flagged for human review rather than dropped entirely.
    assert any(e["stage"] == "evaluate_guardrails" for e in final_state["errors"])
    assert final_state["shortlist"][0].passed_guardrails is False
    assert "guardrail_check_unavailable" in final_state["shortlist"][0].bias_flags


def test_pipeline_records_error_when_question_generation_fails(
    db_session, vector_store, embedding_client, local_storage, open_job
):
    _ingest_candidate_resume(
        db_session, vector_store, embedding_client, local_storage,
        "Asha Kumar", "asha@example.com",
        "Skills: python, fastapi\n4 years of experience.",
    )
    JobIngestionService(db_session, vector_store, embedding_client).ingest(open_job)

    def failing_responder(system_prompt, user_prompt):
        if "designing role-specific interview" in system_prompt:
            return {"questions": []}  # empty -> AgentError
        return _router_responder(system_prompt, user_prompt)

    llm_client = FakeLLMClient(responder=failing_responder)
    pipeline = ShortlistPipeline(db_session, vector_store, embedding_client, llm_client, FakeEnkryptClient())

    final_state = pipeline.run(open_job.id)

    assert any(e["stage"] == "generate_questions" for e in final_state["errors"])
    # Question generation failing must not block the candidate from still
    # getting a recommendation and a shortlist entry (no Interview row, though).
    assert len(final_state["shortlist"]) == 1
    application_id = final_state["shortlist"][0].application_id
    interview = db_session.query(Interview).filter_by(application_id=application_id).one_or_none()
    assert interview is None


def test_pipeline_records_error_when_hr_recommendation_fails(
    db_session, vector_store, embedding_client, local_storage, open_job
):
    _ingest_candidate_resume(
        db_session, vector_store, embedding_client, local_storage,
        "Asha Kumar", "asha@example.com",
        "Skills: python, fastapi\n4 years of experience.",
    )
    JobIngestionService(db_session, vector_store, embedding_client).ingest(open_job)

    def failing_responder(system_prompt, user_prompt):
        if "final hiring recommendation" in system_prompt:
            return {"decision": "not_a_real_decision"}  # invalid enum -> AgentError
        return _router_responder(system_prompt, user_prompt)

    llm_client = FakeLLMClient(responder=failing_responder)
    pipeline = ShortlistPipeline(db_session, vector_store, embedding_client, llm_client, FakeEnkryptClient())

    final_state = pipeline.run(open_job.id)

    assert final_state["shortlist"] == []
    assert any(e["stage"] == "synthesize_recommendations" for e in final_state["errors"])
