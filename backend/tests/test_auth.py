"""Authentication: signup, login, and token verification against real HTTP."""

from __future__ import annotations

from tests.conftest import auth, register


def test_signup_returns_token_and_user(client):
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "New@Example.com", "password": "password123", "full_name": "New User"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    # Email is lowercased on the way in, so login is case-insensitive.
    assert body["user"]["email"] == "new@example.com"
    assert "password" not in response.text
    assert "hashed_password" not in response.text


def test_signup_rejects_duplicate_email(client):
    register(client, email="dup@example.com")
    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "dup@example.com", "password": "password123"},
    )
    assert response.status_code == 400


def test_login_succeeds_and_is_case_insensitive(client):
    register(client, email="login@example.com", password="password123")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "LOGIN@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_rejects_wrong_password(client):
    register(client, email="wrong@example.com", password="password123")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@example.com", "password": "not-the-password"},
    )
    assert response.status_code == 401


def test_login_rejects_unknown_email(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "password123"},
    )
    # Same status and shape as a wrong password: the response must not reveal
    # whether the account exists.
    assert response.status_code == 401


def test_me_returns_current_user(client):
    token, user_id = register(client, email="me@example.com")
    response = client.get("/api/v1/auth/me", headers=auth(token))
    assert response.status_code == 200
    assert response.json()["id"] == user_id


def test_protected_route_rejects_missing_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_protected_route_rejects_malformed_token(client):
    response = client.get("/api/v1/auth/me", headers=auth("not-a-jwt"))
    assert response.status_code == 401


def test_protected_route_rejects_token_signed_with_another_key(client):
    """A token minted with a different secret must not be accepted."""
    import jwt

    forged = jwt.encode({"sub": "1", "exp": 9999999999}, "some-other-secret", algorithm="HS256")
    response = client.get("/api/v1/auth/me", headers=auth(forged))
    assert response.status_code == 401
