import pytest

from app.schemas.evaluation import FairnessCheckResult, GroundingCheckResult
from app.services.enkrypt_client import FakeEnkryptClient

VALID_QUESTIONS = {
    "questions": [
        {"id": "q1", "question": "Explain how you would design a rate limiter.", "category": "system_design"},
    ]
}
VALID_SCORES = {
    "per_question": [{"question_id": "q1", "score": 8.0, "feedback": "Strong answer."}],
    "score_breakdown": {"technical": 82, "communication": 78, "problem_solving": 85, "confidence": 74, "leadership": 60},
    "overall_score": 80,
    "summary": "Strong technical performance.",
}
STRONG_HIRE = {
    "decision": "strong_hire",
    "summary": "Excellent candidate.",
    "rationale": "High match score and strong interview performance.",
}


def _bridge_router(system_prompt: str, user_prompt: str) -> dict:
    if "designing role-specific interview" in system_prompt:
        return VALID_QUESTIONS
    if "scoring a candidate's interview" in system_prompt:
        return VALID_SCORES
    if "final hiring recommendation" in system_prompt:
        return STRONG_HIRE
    raise AssertionError(f"Unexpected prompt: {system_prompt[:60]}")


@pytest.fixture()
def auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "bridge-recruiter@talentflow.ai", "password": "supersecret123", "full_name": "Bridge Recruiter"},
    )
    login = client.post("/api/v1/auth/login", json={"email": "bridge-recruiter@talentflow.ai", "password": "supersecret123"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_candidate_search_requires_auth(client):
    response = client.post("/api/v1/candidate/search", json={"job_title": "Backend Engineer"})
    assert response.status_code == 401


def test_candidate_search_returns_empty_when_no_resumes(client, auth_headers):
    response = client.post(
        "/api/v1/candidate/search",
        json={"job_title": "Backend Engineer", "job_description": "Build APIs", "job_skills": ["python"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == {"matches": []}


def test_candidate_search_finds_uploaded_resume(client, auth_headers, embedding_client, vector_store):
    vector_store.upsert_resume(
        "resume-1", "candidate-1", embedding_client.embed_one("Skills: python, fastapi"), {"skills": ["python", "fastapi"]}
    )
    response = client.post(
        "/api/v1/candidate/search",
        json={"job_title": "Backend Engineer", "job_description": "Build APIs with Python", "job_skills": ["python"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    matches = response.json()["matches"]
    assert len(matches) == 1
    assert matches[0]["resume_id"] == "resume-1"


def test_candidate_rank_blends_semantic_and_skill_overlap(client, auth_headers, embedding_client, vector_store):
    vector_store.upsert_resume(
        "resume-1", "candidate-1", embedding_client.embed_one("Skills: python, fastapi"), {"skills": ["python", "fastapi"]}
    )
    response = client.post(
        "/api/v1/candidate/rank",
        json={"job_title": "Backend Engineer", "job_description": "Build APIs", "job_skills": ["python", "fastapi"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    ranked = response.json()
    assert len(ranked) == 1
    assert ranked[0]["match_score"] > 0
    assert "python" in ranked[0]["matched_skills"]


def test_interview_generate(client, auth_headers, llm_client):
    llm_client.responder = _bridge_router
    response = client.post(
        "/api/v1/interview/generate",
        json={"job_title": "Backend Engineer", "job_skills": ["python"], "num_questions": 1},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert len(response.json()["questions"]) == 1


def test_interview_generate_rejects_empty_title(client, auth_headers, llm_client):
    llm_client.responder = _bridge_router
    response = client.post(
        "/api/v1/interview/generate", json={"job_title": "", "job_skills": []}, headers=auth_headers
    )
    # AgentError from empty title -> 502 per main.py's AgentError handler
    assert response.status_code == 502


def test_interview_evaluate(client, auth_headers, llm_client):
    llm_client.responder = _bridge_router
    response = client.post(
        "/api/v1/interview/evaluate",
        json={
            "job_title": "Backend Engineer",
            "qa_pairs": [{"question_id": "q1", "question": "Design a rate limiter.", "answer": "Token bucket..."}],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["overall_score"] == 80


def test_recommendation(client, auth_headers, llm_client):
    llm_client.responder = _bridge_router
    response = client.post(
        "/api/v1/recommendation",
        json={
            "candidate_name": "Asha Kumar",
            "match_score": 90,
            "match_rationale": "Strong overlap",
            "guardrails_passed": True,
            "bias_flags": [],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "strong_hire"


def test_recommendation_forces_hold_when_guardrails_failed(client, auth_headers, llm_client):
    """The bridge endpoint must preserve the exact same safety override as the internal agent -
    this is not reimplemented here, just called through, so this test is really confirming the
    wiring didn't accidentally bypass it."""
    llm_client.responder = _bridge_router
    response = client.post(
        "/api/v1/recommendation",
        json={
            "candidate_name": "Asha Kumar",
            "match_score": 90,
            "match_rationale": "Strong overlap",
            "guardrails_passed": False,
            "bias_flags": ["some_flag"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "hold"


def test_enkrypt_check_fairness_only(client, auth_headers):
    response = client.post(
        "/api/v1/enkrypt/check", json={"text": "This candidate has strong technical skills."}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["passed_guardrails"] is True
    assert body["grounding_score"] == 1.0


def test_enkrypt_check_with_grounding(client, auth_headers, enkrypt_client):
    def failing_grounding(claim, source):
        return GroundingCheckResult(grounding_score=0.2, ungrounded_claims=["unsupported claim"], passed=False)

    # Override the fixture's enkrypt client responder for this test only.
    enkrypt_client._grounding_responder = failing_grounding

    response = client.post(
        "/api/v1/enkrypt/check",
        json={"text": "Candidate has 10 years experience.", "source_text": "Resume shows 3 years experience."},
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["passed_guardrails"] is False
    assert "unsupported claim" in body["bias_flags"]
