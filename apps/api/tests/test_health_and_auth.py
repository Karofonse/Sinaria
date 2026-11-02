from tests.conftest import new_email, register_user


def test_liveness_and_readiness(client):
    assert client.get("/v1/health").json() == {"status": "ok"}
    ready = client.get("/v1/health/ready").json()
    assert ready["checks"]["database"] == "ok"
    assert ready["checks"]["redis"] == "ok"


def test_register_sets_httponly_session_and_creates_user(client):
    info = register_user(client)
    me = client.get("/v1/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == info["email"]
    assert body["roles"] == ["user"]
    assert "password" not in body and "password_hash" not in body
    set_cookie = client.cookies.jar  # cookie presente en el jar del cliente
    assert any(c.name == "sonaria_session" for c in set_cookie)


def test_duplicate_email_is_rejected(client):
    info = register_user(client)
    client.cookies.clear()
    resp = client.post(
        "/v1/auth/register",
        json={"email": info["email"], "password": "otra-contraseña-123", "display_name": "Otro"},
    )
    assert resp.status_code == 409


def test_weak_password_is_rejected_by_validation(client):
    resp = client.post("/v1/auth/register", json={"email": new_email(), "password": "corta", "display_name": "Ana"})
    assert resp.status_code == 422


def test_unknown_fields_are_rejected(client):
    resp = client.post(
        "/v1/auth/register",
        json={"email": new_email(), "password": "contraseña-segura-123", "display_name": "Ana", "roles": ["admin"]},
    )
    assert resp.status_code == 422


def test_login_wrong_password_is_generic(client):
    info = register_user(client)
    client.cookies.clear()
    bad = client.post("/v1/auth/login", json={"email": info["email"], "password": "incorrecta-123"})
    unknown = client.post("/v1/auth/login", json={"email": new_email(), "password": "incorrecta-123"})
    assert bad.status_code == unknown.status_code == 401
    assert bad.json()["detail"]["message"] == unknown.json()["detail"]["message"]


def test_login_then_logout(client):
    info = register_user(client)
    client.cookies.clear()
    assert client.get("/v1/auth/me").status_code == 401
    assert client.post("/v1/auth/login", json={"email": info["email"], "password": info["password"]}).status_code == 200
    assert client.get("/v1/auth/me").status_code == 200
    assert client.post("/v1/auth/logout").status_code == 204
    client.cookies.clear()
    assert client.get("/v1/auth/me").status_code == 401


def test_mutation_without_json_content_type_is_refused(client):
    register_user(client)
    resp = client.post(
        "/v1/generations",
        data="prompt=x",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Idempotency-Key": "abcdefgh-1"},
    )
    assert resp.status_code == 415


def test_bearer_token_is_accepted(client):
    info = register_user(client)
    token = [c.value for c in client.cookies.jar if c.name == "sonaria_session"][0]
    client.cookies.clear()
    resp = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200 and resp.json()["email"] == info["email"]


def test_tampered_token_is_rejected(client):
    register_user(client)
    token = [c.value for c in client.cookies.jar if c.name == "sonaria_session"][0]
    client.cookies.clear()
    resp = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token[:-4]}AAAA"})
    assert resp.status_code == 401
