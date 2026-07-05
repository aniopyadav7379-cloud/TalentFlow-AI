import pytest


@pytest.fixture()
def auth_headers(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "jobs-recruiter@talentflow.ai", "password": "supersecret123", "full_name": "Jobs Recruiter"},
    )
    login = client.post("/api/v1/auth/login", json={"email": "jobs-recruiter@talentflow.ai", "password": "supersecret123"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


JOB_PAYLOAD = {
    "title": "Backend Engineer",
    "description": "Build and scale REST APIs using Python and FastAPI.",
    "skills": ["python", "fastapi", "postgresql"],
    "location": "Remote",
}


def test_create_job_requires_auth(client):
    response = client.post("/api/v1/jobs", json=JOB_PAYLOAD)
    assert response.status_code == 401


def test_create_job_succeeds_and_embeds(client, auth_headers):
    response = client.post("/api/v1/jobs", json=JOB_PAYLOAD, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Backend Engineer"
    assert data["status"] == "draft"


def test_create_job_rejects_short_description(client, auth_headers):
    bad_payload = dict(JOB_PAYLOAD, description="too short")
    response = client.post("/api/v1/jobs", json=bad_payload, headers=auth_headers)
    assert response.status_code == 422


def test_get_job_by_id(client, auth_headers):
    created = client.post("/api/v1/jobs", json=JOB_PAYLOAD, headers=auth_headers).json()
    response = client.get(f"/api/v1/jobs/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_nonexistent_job_returns_404(client, auth_headers):
    response = client.get("/api/v1/jobs/does-not-exist", headers=auth_headers)
    assert response.status_code == 404


def test_list_jobs_returns_created_jobs(client, auth_headers):
    client.post("/api/v1/jobs", json=JOB_PAYLOAD, headers=auth_headers)
    client.post("/api/v1/jobs", json=dict(JOB_PAYLOAD, title="Frontend Engineer"), headers=auth_headers)

    response = client.get("/api/v1/jobs", headers=auth_headers)
    assert response.status_code == 200
    titles = [j["title"] for j in response.json()]
    assert "Backend Engineer" in titles
    assert "Frontend Engineer" in titles


def test_update_job_status(client, auth_headers):
    created = client.post("/api/v1/jobs", json=JOB_PAYLOAD, headers=auth_headers).json()
    response = client.patch(f"/api/v1/jobs/{created['id']}", json={"status": "open"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "open"


def test_update_nonexistent_job_returns_404(client, auth_headers):
    response = client.patch("/api/v1/jobs/does-not-exist", json={"status": "open"}, headers=auth_headers)
    assert response.status_code == 404


def test_update_job_skills_triggers_re_embed(client, auth_headers):
    created = client.post("/api/v1/jobs", json=JOB_PAYLOAD, headers=auth_headers).json()
    response = client.patch(
        f"/api/v1/jobs/{created['id']}", json={"skills": ["python", "go", "kubernetes"]}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["skills"] == ["python", "go", "kubernetes"]


def test_update_job_location_only_does_not_require_re_embed(client, auth_headers):
    """Updating a field that isn't part of the embedding text (location) should still succeed
    without needing to touch the re-embed path."""
    created = client.post("/api/v1/jobs", json=JOB_PAYLOAD, headers=auth_headers).json()
    response = client.patch(f"/api/v1/jobs/{created['id']}", json={"location": "Hyderabad"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["location"] == "Hyderabad"
