import io

import pytest

from tests.pdf_helpers import make_pdf_bytes


@pytest.fixture()
def auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "cand-recruiter@talentflow.ai", "password": "supersecret123", "full_name": "Recruiter"},
    )
    login = client.post("/api/v1/auth/login", json={"email": "cand-recruiter@talentflow.ai", "password": "supersecret123"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_create_candidate(client, auth_headers):
    response = client.post(
        "/api/v1/candidates",
        json={"full_name": "Asha Kumar", "email": "asha@example.com", "phone": "+91 98765 43210"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["full_name"] == "Asha Kumar"


def test_create_candidate_rejects_duplicate_email(client, auth_headers):
    payload = {"full_name": "Asha Kumar", "email": "dup-candidate@example.com"}
    client.post("/api/v1/candidates", json=payload, headers=auth_headers)
    second = client.post("/api/v1/candidates", json=payload, headers=auth_headers)
    assert second.status_code == 409


def test_get_candidate(client, auth_headers):
    created = client.post(
        "/api/v1/candidates", json={"full_name": "Ravi Sharma", "email": "ravi@example.com"}, headers=auth_headers
    ).json()
    response = client.get(f"/api/v1/candidates/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "ravi@example.com"


def test_get_nonexistent_candidate_returns_404(client, auth_headers):
    response = client.get("/api/v1/candidates/does-not-exist", headers=auth_headers)
    assert response.status_code == 404


def test_upload_resume_ingests_successfully(client, auth_headers):
    candidate = client.post(
        "/api/v1/candidates", json={"full_name": "Asha Kumar", "email": "asha-resume@example.com"}, headers=auth_headers
    ).json()

    pdf_bytes = make_pdf_bytes("Skills: python, fastapi, postgresql\n5 years of backend experience.")
    response = client.post(
        f"/api/v1/candidates/{candidate['id']}/resume",
        files={"file": ("resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["parse_status"] == "parsed"
    assert "python" in data["parsed_skills"]


def test_upload_resume_rejects_non_pdf(client, auth_headers):
    candidate = client.post(
        "/api/v1/candidates", json={"full_name": "Asha Kumar", "email": "asha-badfile@example.com"}, headers=auth_headers
    ).json()

    response = client.post(
        f"/api/v1/candidates/{candidate['id']}/resume",
        files={"file": ("resume.txt", io.BytesIO(b"not a pdf"), "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == 415


def test_upload_resume_for_nonexistent_candidate_returns_404(client, auth_headers):
    pdf_bytes = make_pdf_bytes("Some resume text.")
    response = client.post(
        "/api/v1/candidates/does-not-exist/resume",
        files={"file": ("resume.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_upload_resume_rejects_file_over_size_limit(client, auth_headers):
    candidate = client.post(
        "/api/v1/candidates", json={"full_name": "Asha Kumar", "email": "asha-toolarge@example.com"}, headers=auth_headers
    ).json()

    oversized_content = b"%PDF-1.4\n" + (b"0" * (10 * 1024 * 1024 + 1))
    response = client.post(
        f"/api/v1/candidates/{candidate['id']}/resume",
        files={"file": ("resume.pdf", io.BytesIO(oversized_content), "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 413
