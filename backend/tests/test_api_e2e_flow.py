import io

import pytest

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
VALID_SCORES = {
    "per_question": [
        {"question_id": "q1", "score": 8.0, "feedback": "Strong answer."},
        {"question_id": "q2", "score": 7.5, "feedback": "Good, specific example."},
    ],
    "score_breakdown": {"technical": 82, "communication": 78, "problem_solving": 85, "confidence": 74, "leadership": 60},
    "overall_score": 80,
    "summary": "Strong technical performance throughout the interview.",
}


def _full_router(system_prompt: str, user_prompt: str) -> dict:
    if "analyzing a resume" in system_prompt:
        return VALID_ANALYSIS
    if "designing role-specific interview" in system_prompt:
        return VALID_QUESTIONS
    if "scoring a candidate's interview" in system_prompt:
        return VALID_SCORES
    if "final hiring recommendation" in system_prompt:
        return STRONG_HIRE
    raise AssertionError(f"Unexpected prompt reached test router: {system_prompt[:80]}")


@pytest.fixture()
def auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "e2e-recruiter@talentflow.ai", "password": "supersecret123", "full_name": "E2E Recruiter"},
    )
    login = client.post("/api/v1/auth/login", json={"email": "e2e-recruiter@talentflow.ai", "password": "supersecret123"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_full_recruitment_flow_end_to_end(client, auth_headers, llm_client):
    llm_client.responder = _full_router

    # 1. Create and embed a job.
    job = client.post(
        "/api/v1/jobs",
        json={
            "title": "Backend Engineer",
            "description": "Build and scale REST APIs using Python and FastAPI.",
            "skills": ["python", "fastapi", "postgresql"],
        },
        headers=auth_headers,
    ).json()

    # 2. Create a candidate and upload their resume.
    candidate = client.post(
        "/api/v1/candidates", json={"full_name": "Asha Kumar", "email": "asha-e2e@example.com"}, headers=auth_headers
    ).json()
    pdf_bytes = make_pdf_bytes("Skills: python, fastapi, postgresql\n5 years of backend engineering experience.")
    resume_response = client.post(
        f"/api/v1/candidates/{candidate['id']}/resume",
        files={"file": ("resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=auth_headers,
    )
    assert resume_response.status_code == 201

    # 3. Run the shortlist pipeline for the job.
    shortlist_response = client.post(f"/api/v1/jobs/{job['id']}/shortlist", json={"top_k": 5}, headers=auth_headers)
    assert shortlist_response.status_code == 200
    shortlist = shortlist_response.json()
    assert len(shortlist) == 1
    entry = shortlist[0]
    assert entry["candidate_id"] == candidate["id"]
    assert entry["passed_guardrails"] is True
    application_id = entry["application_id"]

    # 4. List applications for the job — should include the one just created.
    applications = client.get(f"/api/v1/jobs/{job['id']}/applications", headers=auth_headers).json()
    assert len(applications) == 1
    assert applications[0]["id"] == application_id

    # 5. Fetch the AI-generated interview questions.
    interview_response = client.get(f"/api/v1/applications/{application_id}/interview", headers=auth_headers)
    assert interview_response.status_code == 200
    interview = interview_response.json()
    assert interview["status"] == "pending"
    assert len(interview["questions"]) == 2

    # 6. Submit interview responses -> triggers scoring + re-evaluation.
    submit_response = client.post(
        f"/api/v1/applications/{application_id}/interview/responses",
        json={
            "responses": [
                {"question_id": "q1", "question": "Explain how you would design a rate limiter.", "answer": "Token bucket algorithm..."},
                {"question_id": "q2", "question": "Describe a challenging bug you fixed.", "answer": "A race condition in..."},
            ]
        },
        headers=auth_headers,
    )
    assert submit_response.status_code == 200
    completed_interview = submit_response.json()
    assert completed_interview["status"] == "completed"
    assert completed_interview["overall_score"] == 80

    # 7. Application status should now reflect the interview happened.
    application = client.get(f"/api/v1/applications/{application_id}", headers=auth_headers).json()
    assert application["status"] == "interviewing"


def test_shortlist_requires_auth(client):
    response = client.post("/api/v1/jobs/some-job-id/shortlist", json={})
    assert response.status_code == 401


def test_shortlist_for_nonexistent_job_returns_404(client, auth_headers):
    response = client.post("/api/v1/jobs/does-not-exist/shortlist", json={}, headers=auth_headers)
    assert response.status_code == 404


def test_get_interview_before_shortlist_returns_404(client, auth_headers):
    response = client.get("/api/v1/applications/nonexistent-application/interview", headers=auth_headers)
    assert response.status_code == 404


def test_submit_responses_with_missing_fields_returns_422(client, auth_headers):
    response = client.post(
        "/api/v1/applications/some-id/interview/responses",
        json={"responses": [{"question_id": "q1"}]},  # missing "question" and "answer"
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_list_applications_for_nonexistent_job_returns_404(client, auth_headers):
    response = client.get("/api/v1/jobs/does-not-exist/applications", headers=auth_headers)
    assert response.status_code == 404


def test_get_nonexistent_application_returns_404(client, auth_headers):
    response = client.get("/api/v1/applications/does-not-exist", headers=auth_headers)
    assert response.status_code == 404


def test_list_applications_empty_for_job_with_no_shortlist_run(client, auth_headers):
    job = client.post(
        "/api/v1/jobs",
        json={"title": "Empty Role", "description": "A role nobody applied to yet, still long enough."},
        headers=auth_headers,
    ).json()
    response = client.get(f"/api/v1/jobs/{job['id']}/applications", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_submit_responses_for_nonexistent_application_returns_404(client, auth_headers, llm_client):
    llm_client.responder = _full_router
    response = client.post(
        "/api/v1/applications/does-not-exist/interview/responses",
        json={"responses": [{"question_id": "q1", "question": "Q?", "answer": "A."}]},
        headers=auth_headers,
    )
    assert response.status_code == 404
