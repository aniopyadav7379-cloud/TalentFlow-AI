def test_register_creates_user(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "recruiter@talentflow.ai", "password": "supersecret123", "full_name": "Recruiter One"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "recruiter@talentflow.ai"
    assert "password" not in data
    assert "hashed_password" not in data


def test_register_rejects_duplicate_email(client):
    payload = {"email": "dup@talentflow.ai", "password": "supersecret123", "full_name": "Dup User"}
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


def test_register_rejects_short_password(client):
    response = client.post(
        "/api/v1/auth/register", json={"email": "short@talentflow.ai", "password": "short", "full_name": "Short Pw"}
    )
    assert response.status_code == 422


def test_login_returns_valid_token(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "login@talentflow.ai", "password": "supersecret123", "full_name": "Login User"},
    )
    response = client.post("/api/v1/auth/login", json={"email": "login@talentflow.ai", "password": "supersecret123"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_rejects_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "wrongpw@talentflow.ai", "password": "supersecret123", "full_name": "User"},
    )
    response = client.post("/api/v1/auth/login", json={"email": "wrongpw@talentflow.ai", "password": "nope"})
    assert response.status_code == 401


def test_login_rejects_unknown_email(client):
    response = client.post("/api/v1/auth/login", json={"email": "ghost@talentflow.ai", "password": "whatever123"})
    assert response.status_code == 401


def test_me_requires_authentication(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user_with_valid_token(client):
    client.post(
        "/api/v1/auth/register", json={"email": "me@talentflow.ai", "password": "supersecret123", "full_name": "Me User"}
    )
    login = client.post("/api/v1/auth/login", json={"email": "me@talentflow.ai", "password": "supersecret123"})
    token = login.json()["access_token"]

    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@talentflow.ai"


def test_me_rejects_tampered_token(client):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.valid.token"})
    assert response.status_code == 401
