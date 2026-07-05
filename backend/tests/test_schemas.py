import pytest
from pydantic import ValidationError

from app.schemas.application import EvaluationOut, ShortlistEntry
from app.schemas.candidate import CandidateCreate
from app.schemas.job import JobCreate


def test_job_create_requires_min_description_length():
    with pytest.raises(ValidationError):
        JobCreate(title="Engineer", description="too short")


def test_job_create_valid_payload():
    job = JobCreate(
        title="Backend Engineer",
        description="Design and build scalable REST APIs for our platform.",
        skills=["python", "fastapi", "postgres"],
    )
    assert job.skills == ["python", "fastapi", "postgres"]
    assert job.salary_min is None


def test_job_create_rejects_negative_salary():
    with pytest.raises(ValidationError):
        JobCreate(
            title="Backend Engineer",
            description="Design and build scalable REST APIs for our platform.",
            salary_min=-1000,
        )


def test_candidate_create_validates_email():
    with pytest.raises(ValidationError):
        CandidateCreate(full_name="Asha Kumar", email="not-an-email")

    candidate = CandidateCreate(full_name="Asha Kumar", email="asha@example.com")
    assert candidate.email == "asha@example.com"


def test_shortlist_entry_match_score_bounds():
    with pytest.raises(ValidationError):
        ShortlistEntry(
            application_id="a1",
            candidate_id="c1",
            candidate_name="Asha",
            match_score=150,  # out of 0-100 bounds
            match_rationale="Strong fit",
            passed_guardrails=True,
            recommendation="Proceed to interview",
        )


def test_shortlist_entry_valid():
    entry = ShortlistEntry(
        application_id="a1",
        candidate_id="c1",
        candidate_name="Asha",
        match_score=92.5,
        match_rationale="Strong Python + system design background",
        top_skills=["python", "distributed systems"],
        passed_guardrails=True,
        bias_flags=[],
        recommendation="Proceed to interview",
    )
    assert entry.match_score == 92.5
    assert entry.bias_flags == []


def test_evaluation_out_from_orm_like_object():
    class FakeORM:
        id = "e1"
        application_id = "a1"
        fairness_score = 0.95
        bias_flags = []
        grounding_score = 0.99
        passed_guardrails = True
        final_recommendation = "Proceed"
        created_at = __import__("datetime").datetime(2026, 1, 1)

    result = EvaluationOut.model_validate(FakeORM())
    assert result.passed_guardrails is True
