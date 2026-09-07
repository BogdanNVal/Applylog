from tests.conftest import PASSWORD


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_signs_the_user_in(client):
    response = client.post(
        "/api/auth/register", json={"email": "New@Example.com", "password": PASSWORD}
    )
    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"

    assert client.get("/api/auth/me").json()["email"] == "new@example.com"


def test_register_rejects_a_duplicate_email(client):
    payload = {"email": "taken@example.com", "password": PASSWORD}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_register_rejects_a_short_password(client):
    response = client.post(
        "/api/auth/register", json={"email": "short@example.com", "password": "1234567"}
    )
    assert response.status_code == 422


def test_register_rejects_an_invalid_email(client):
    response = client.post(
        "/api/auth/register", json={"email": "not-an-email", "password": PASSWORD}
    )
    assert response.status_code == 422


def test_login_with_the_wrong_password_is_rejected(client):
    client.post(
        "/api/auth/register", json={"email": "user@example.com", "password": PASSWORD}
    )
    client.post("/api/auth/logout")

    response = client.post(
        "/api/auth/login", json={"email": "user@example.com", "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_login_is_case_insensitive_for_the_email(client):
    client.post(
        "/api/auth/register", json={"email": "user@example.com", "password": PASSWORD}
    )
    client.post("/api/auth/logout")

    response = client.post(
        "/api/auth/login", json={"email": "USER@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200


def test_logout_ends_the_session(signed_in):
    assert signed_in.post("/api/auth/logout").status_code == 204
    assert signed_in.get("/api/auth/me").status_code == 401


def test_password_is_not_stored_in_plain_text(client):
    from app.db import pool

    client.post(
        "/api/auth/register", json={"email": "user@example.com", "password": PASSWORD}
    )

    with pool().connection() as conn:
        stored = conn.execute("SELECT password_hash FROM users").fetchone()[
            "password_hash"
        ]

    assert PASSWORD not in stored
    assert stored.startswith("pbkdf2_sha256$")
