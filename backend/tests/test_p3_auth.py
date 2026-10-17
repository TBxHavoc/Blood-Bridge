"""P3: authentication and RBAC."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import auth_header


def test_login_success(client: TestClient, admin_token: str) -> None:
    assert admin_token


def test_login_wrong_password_401(client: TestClient) -> None:
    from tests.conftest import _ensure_user

    _ensure_user("pytest_wrong", "admin")
    resp = client.post(
        "/api/v1/auth/login", json={"username": "pytest_wrong", "password": "nope"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_me_requires_token(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_user(client: TestClient, admin_token: str) -> None:
    resp = client.get("/api/v1/auth/me", headers=auth_header(admin_token))
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "admin"


def test_rbac_admin_only_forbidden_for_hospital(
    client: TestClient, hospital_token: str
) -> None:
    resp = client.get("/api/v1/admin/users", headers=auth_header(hospital_token))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_list_users(client: TestClient, admin_token: str) -> None:
    resp = client.get("/api/v1/admin/users", headers=auth_header(admin_token))
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


def test_config_admin_only(client: TestClient, hospital_token: str) -> None:
    resp = client.get("/api/v1/config", headers=auth_header(hospital_token))
    assert resp.status_code == 403


def test_no_public_registration(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/register", json={"username": "x", "password": "y"}
    )
    assert resp.status_code == 404


def test_login_is_rate_limited(client: TestClient) -> None:
    from tests.conftest import _ensure_user

    _ensure_user("pytest_rl", "admin")
    statuses = [
        client.post(
            "/api/v1/auth/login", json={"username": "pytest_rl", "password": "bad"}
        ).status_code
        for _ in range(13)
    ]
    assert 429 in statuses
