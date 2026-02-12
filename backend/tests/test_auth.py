def test_login_success(client, admin_user):
    resp = client.post(
        "/api/auth/login",
        json={"email": "testadmin@premia.co.ke", "password": "Admin@2026"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "testadmin@premia.co.ke"
    assert data["user"]["role"] == "super_admin"


def test_login_invalid_password(client, admin_user):
    resp = client.post(
        "/api/auth/login",
        json={"email": "testadmin@premia.co.ke", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.get_json()["error"] == "Invalid email or password"


def test_login_missing_fields(client):
    resp = client.post("/api/auth/login", json={"email": "a@b.com"})
    assert resp.status_code == 400


def test_me_endpoint(client, admin_headers):
    resp = client.get("/api/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.get_json()["user"]["email"] == "testadmin@premia.co.ke"


def test_me_without_auth(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_register_requires_admin(client, coach_headers):
    resp = client.post(
        "/api/auth/register",
        headers=coach_headers,
        json={
            "email": "new@premia.co.ke",
            "password": "Test@1234",
            "first_name": "New",
            "last_name": "User",
            "role": "player",
        },
    )
    assert resp.status_code == 403


def test_register_success(client, admin_headers):
    resp = client.post(
        "/api/auth/register",
        headers=admin_headers,
        json={
            "email": "new@premia.co.ke",
            "password": "Test@1234",
            "first_name": "New",
            "last_name": "User",
            "role": "player",
        },
    )
    assert resp.status_code == 201
    assert resp.get_json()["user"]["email"] == "new@premia.co.ke"


def test_register_weak_password(client, admin_headers):
    resp = client.post(
        "/api/auth/register",
        headers=admin_headers,
        json={
            "email": "weak@premia.co.ke",
            "password": "short",
            "first_name": "Weak",
            "last_name": "Pass",
            "role": "player",
        },
    )
    # schema validation catches min length 8
    assert resp.status_code == 400


def test_register_invalid_role(client, admin_headers):
    resp = client.post(
        "/api/auth/register",
        headers=admin_headers,
        json={
            "email": "badrole@premia.co.ke",
            "password": "Test@1234",
            "first_name": "Bad",
            "last_name": "Role",
            "role": "god_mode",
        },
    )
    assert resp.status_code == 400


def test_refresh_token(client, admin_user):
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "testadmin@premia.co.ke", "password": "Admin@2026"},
    )
    refresh_token = login_resp.get_json()["refresh_token"]

    resp = client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.get_json()
