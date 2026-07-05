import pytest

from app.db.postgres.models import (
    Application,
    ApplicationStatus,
    Candidate,
    Evaluation,
    Interview,
    InterviewResponse,
    InterviewStatus,
    Job,
    JobStatus,
    User,
    UserRole,
)
from app.orchestrator.interview_evaluation_pipeline import InterviewEvaluationPipeline, InterviewPipelineFatalError
from app.schemas.evaluation import GroundingCheckResult
from app.services.enkrypt_client import FakeEnkryptClient
from app.services.llm_client import FakeLLMClient

VALID_SCORES = {
    "per_question": [
        {"question_id": "q1", "score": 8.0, "feedback": "Strong answer."},
        {"question_id": "q2", "score": 7.0, "feedback": "Good, could be more specific."},
    ],
    "score_breakdown": {"technical": 82, "communication": 78, "problem_solving": 85, "confidence": 70, "leadership": 60},
    "overall_score": 79,
    "summary": "Strong technical performance in the interview.",
}

STRONG_HIRE = {
    "decision": "strong_hire",
    "summary": "Excellent candidate overall — recommend proceeding to offer.",
    "rationale": "High resume match combined with strong interview performance across all dimensions.",
}


def _router(system_prompt: str, user_prompt: str) -> dict:
    if "scoring a candidate's interview" in system_prompt:
        return VALID_SCORES
    if "final hiring recommendation" in system_prompt:
        return STRONG_HIRE
    raise AssertionError(f"Unexpected prompt: {system_prompt[:60]}")


@pytest.fixture()
def application_with_pending_interview(db_session):
    user = User(email="r@talentflow.ai", hashed_password="x", full_name="Recruiter", role=UserRole.RECRUITER)
    db_session.add(user)
    db_session.commit()

    job = Job(
        title="Backend Engineer", description="Build APIs.", skills=["python"], status=JobStatus.OPEN, created_by_id=user.id
    )
    db_session.add(job)
    candidate = Candidate(full_name="Asha Kumar", email="asha@example.com")
    db_session.add(candidate)
    db_session.commit()

    application = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        status=ApplicationStatus.SHORTLISTED,
        match_score=85.0,
        match_rationale="Strong skill overlap",
    )
    db_session.add(application)
    db_session.commit()

    interview = Interview(
        application_id=application.id,
        status=InterviewStatus.PENDING,
        questions=[
            {"id": "q1", "question": "Design a rate limiter.", "category": "system_design"},
            {"id": "q2", "question": "Describe a tricky bug you fixed.", "category": "technical"},
        ],
    )
    db_session.add(interview)
    db_session.commit()
    return application


QA_PAIRS = [
    {"question_id": "q1", "question": "Design a rate limiter.", "answer": "I'd use a token bucket algorithm..."},
    {"question_id": "q2", "question": "Describe a tricky bug you fixed.", "answer": "Once I found a race condition..."},
]


def test_run_scores_interview_and_updates_status(db_session, application_with_pending_interview):
    # A passing prior evaluation (from the shortlist stage) so this test
    # isolates scoring/status behavior, not the fail-closed guardrail logic
    # (covered separately below).
    db_session.add(
        Evaluation(application_id=application_with_pending_interview.id, fairness_score=1.0, grounding_score=1.0, passed_guardrails=True)
    )
    db_session.commit()

    pipeline = InterviewEvaluationPipeline(db_session, FakeLLMClient(responder=_router), FakeEnkryptClient())
    result = pipeline.run(application_with_pending_interview.id, QA_PAIRS)

    assert result["interview"].status == InterviewStatus.COMPLETED
    assert result["interview"].overall_score == 79
    assert result["application"].status == ApplicationStatus.INTERVIEWING
    assert result["recommendation"].decision == "strong_hire"


def test_run_with_no_prior_evaluation_fails_closed_to_hold(db_session, application_with_pending_interview):
    """No prior Evaluation row exists (the shortlist guardrail check never ran or wasn't found) —
    the pipeline must fail closed rather than assume the candidate is clear."""
    pipeline = InterviewEvaluationPipeline(db_session, FakeLLMClient(responder=_router), FakeEnkryptClient())
    result = pipeline.run(application_with_pending_interview.id, QA_PAIRS)

    assert result["recommendation"].decision == "hold"
    evaluation = db_session.query(Evaluation).filter_by(application_id=application_with_pending_interview.id).one()
    assert "no_prior_evaluation" in evaluation.bias_flags


def test_run_persists_interview_responses(db_session, application_with_pending_interview):
    pipeline = InterviewEvaluationPipeline(db_session, FakeLLMClient(responder=_router), FakeEnkryptClient())
    result = pipeline.run(application_with_pending_interview.id, QA_PAIRS)

    responses = db_session.query(InterviewResponse).filter_by(interview_id=result["interview"].id).all()
    assert len(responses) == 2
    scores = {r.question: r.score for r in responses}
    assert scores["Design a rate limiter."] == 8.0


def test_run_raises_fatal_error_for_unknown_application(db_session):
    pipeline = InterviewEvaluationPipeline(db_session, FakeLLMClient(responder=_router), FakeEnkryptClient())
    with pytest.raises(InterviewPipelineFatalError):
        pipeline.run("nonexistent-application-id", QA_PAIRS)


def test_run_raises_fatal_error_when_no_interview_exists(db_session):
    user = User(email="r2@talentflow.ai", hashed_password="x", full_name="Recruiter", role=UserRole.RECRUITER)
    db_session.add(user)
    db_session.commit()
    job = Job(title="QA Engineer", description="Test things.", status=JobStatus.OPEN, created_by_id=user.id)
    db_session.add(job)
    candidate = Candidate(full_name="Ravi", email="ravi2@example.com")
    db_session.add(candidate)
    db_session.commit()
    application = Application(job_id=job.id, candidate_id=candidate.id)
    db_session.add(application)
    db_session.commit()

    pipeline = InterviewEvaluationPipeline(db_session, FakeLLMClient(responder=_router), FakeEnkryptClient())
    with pytest.raises(InterviewPipelineFatalError):
        pipeline.run(application.id, QA_PAIRS)


def test_post_hoc_guardrail_failure_forces_hold_even_if_llm_says_strong_hire(db_session, application_with_pending_interview):
    def failing_grounding(claim, source):
        return GroundingCheckResult(grounding_score=0.1, ungrounded_claims=["overstates interview performance"], passed=False)

    enkrypt_client = FakeEnkryptClient(grounding_responder=failing_grounding)
    pipeline = InterviewEvaluationPipeline(db_session, FakeLLMClient(responder=_router), enkrypt_client)
    result = pipeline.run(application_with_pending_interview.id, QA_PAIRS)

    assert result["recommendation"].decision == "hold"
    assert "Held for human review" in result["recommendation"].summary

    evaluation = db_session.query(Evaluation).filter_by(application_id=application_with_pending_interview.id).one()
    assert evaluation.passed_guardrails is False
    assert "overstates interview performance" not in evaluation.bias_flags  # that flag lives in ungrounded_claims, not bias_flags
    assert evaluation.grounding_score == 0.1


def test_carries_forward_prior_evaluation_bias_flags(db_session, application_with_pending_interview):
    # Simulate a prior Evaluation row from the shortlist pipeline stage with a bias flag already on record.
    prior = Evaluation(
        application_id=application_with_pending_interview.id,
        fairness_score=0.6,
        bias_flags=["prior_flag_from_resume_stage"],
        grounding_score=1.0,
        passed_guardrails=False,
    )
    db_session.add(prior)
    db_session.commit()

    pipeline = InterviewEvaluationPipeline(db_session, FakeLLMClient(responder=_router), FakeEnkryptClient())
    result = pipeline.run(application_with_pending_interview.id, QA_PAIRS)

    # Prior guardrail failure must still force "hold" even though the
    # post-hoc check on the new rationale passes cleanly.
    assert result["recommendation"].decision == "hold"
    evaluation = db_session.query(Evaluation).filter_by(application_id=application_with_pending_interview.id).one()
    assert "prior_flag_from_resume_stage" in evaluation.bias_flags
