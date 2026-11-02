import time
import uuid

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.worker import run_job
from tests.conftest import make_admin, register_user
from tests.test_generations import _post


def _completed_track(client, key: str) -> dict:
    job_id = _post(client, key=key).json()["id"]
    assert run_job(uuid.UUID(job_id)) == "completed"
    tracks = client.get("/v1/tracks").json()
    return next(t for t in tracks if t["generation_job_id"] == job_id)


def _setup_owner(client, user_with_credits, monkeypatch, key):
    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: None)
    user_with_credits(10)
    return _completed_track(client, key)


def test_library_lists_renames_searches_and_deletes(client, user_with_credits, monkeypatch):
    track = _setup_owner(client, user_with_credits, monkeypatch, "key-lib-000001")
    assert track["title"].startswith("ambient")

    assert client.get("/v1/tracks", params={"q": "PIANO"}).json() != []
    assert client.get("/v1/tracks", params={"q": "no-existe-xyz"}).json() == []

    renamed = client.patch(f"/v1/tracks/{track['id']}", json={"title": "  Mi   tema  "})
    assert renamed.status_code == 200 and renamed.json()["title"] == "Mi tema"

    assert client.delete(f"/v1/tracks/{track['id']}").status_code == 204
    assert client.get(f"/v1/tracks/{track['id']}").status_code == 404
    assert client.get("/v1/tracks").json() == []


def test_search_treats_wildcards_literally(client, user_with_credits, monkeypatch):
    _setup_owner(client, user_with_credits, monkeypatch, "key-wild-000001")
    assert client.get("/v1/tracks", params={"q": "%"}).json() == []


def test_other_users_cannot_access_track(client, user_with_credits, monkeypatch):
    track = _setup_owner(client, user_with_credits, monkeypatch, "key-iso-0000001")
    client.cookies.clear()
    register_user(client)
    assert client.get(f"/v1/tracks/{track['id']}").status_code == 404
    assert client.patch(f"/v1/tracks/{track['id']}", json={"title": "robado"}).status_code == 404
    assert client.delete(f"/v1/tracks/{track['id']}").status_code == 404
    assert client.get(f"/v1/tracks/{track['id']}/download-url").status_code == 404


def test_signed_download_works_and_rejects_tampering(client, user_with_credits, monkeypatch):
    track = _setup_owner(client, user_with_credits, monkeypatch, "key-dl-00000001")
    link = client.get(f"/v1/tracks/{track['id']}/download-url").json()["url"]
    ok = client.get(link)
    assert ok.status_code == 200
    assert ok.headers["content-type"] == "audio/wav"
    assert "attachment" in ok.headers["content-disposition"]
    assert ok.headers["cache-control"] == "private, no-store"

    tampered = link.replace("sig=", "sig=00")
    assert client.get(tampered).status_code == 404
    other_track = link.replace(track["id"], str(uuid.uuid4()))
    assert client.get(other_track).status_code == 404


def test_signed_download_expires(client, user_with_credits, monkeypatch):
    track = _setup_owner(client, user_with_credits, monkeypatch, "key-exp-00000001")
    link = client.get(f"/v1/tracks/{track['id']}/download-url").json()["url"]
    expired = link.split("expires=")[0] + f"expires={int(time.time()) - 5}" + "&sig=" + link.split("sig=")[1]
    assert client.get(expired).status_code == 404


def test_download_is_not_possible_without_signature(client, user_with_credits, monkeypatch):
    track = _setup_owner(client, user_with_credits, monkeypatch, "key-nosig-000001")
    assert client.get(f"/v1/tracks/{track['id']}/file").status_code == 422


def test_non_admin_gets_403_on_admin_routes(client, user_with_credits):
    user_with_credits(1)
    assert client.get("/v1/admin/users").status_code == 403
    assert client.get("/v1/admin/metrics").status_code == 403
    assert client.post(f"/v1/admin/users/{uuid.uuid4()}/suspend", json={"reason": "motivo válido"}).status_code == 403


def test_admin_suspend_blocks_existing_session_and_is_audited(client, user_with_credits):
    target = user_with_credits(3)
    token = [c.value for c in client.cookies.jar if c.name == "sonaria_session"][0]
    admin = register_user(client)
    make_admin(admin["id"])
    client.cookies.clear()
    client.post("/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    assert client.get("/v1/admin/users").status_code == 200

    resp = client.post(f"/v1/admin/users/{target['id']}/suspend", json={"reason": "Abuso confirmado en soporte"})
    assert resp.status_code == 200 and resp.json()["status"] == "suspended"

    with SessionLocal() as db:
        n = db.execute(
            text("SELECT count(*) FROM admin_audit_logs WHERE action='user.suspend' AND target_id=:t"),
            {"t": target["id"]},
        ).scalar_one()
    assert n == 1

    # Una sesión abierta antes de la suspensión debe dejar de funcionar de inmediato.
    client.cookies.clear()
    assert client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    # Y no se puede iniciar sesión de nuevo.
    assert (
        client.post("/v1/auth/login", json={"email": target["email"], "password": target["password"]}).status_code
        == 403
    )


def test_admin_credit_adjustment_is_idempotent_and_audited(client, user_with_credits):
    target = user_with_credits(0)
    admin = register_user(client)
    make_admin(admin["id"])
    client.cookies.clear()
    client.post("/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})

    body = {"delta": 25, "reason": "Compensación por fallo de servicio", "idempotency_key": "adj-0000000001"}
    first = client.post(f"/v1/admin/users/{target['id']}/credit-adjustments", json=body)
    again = client.post(f"/v1/admin/users/{target['id']}/credit-adjustments", json=body)
    assert first.json() == {"applied": True, "available_credits": 25, "reserved_credits": 0}
    assert again.json() == {"applied": False, "available_credits": 25, "reserved_credits": 0}


def test_admin_cannot_make_balance_negative(client, user_with_credits):
    target = user_with_credits(2)
    admin = register_user(client)
    make_admin(admin["id"])
    client.cookies.clear()
    client.post("/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
    body = {"delta": -5, "reason": "Corrección de saldo", "idempotency_key": "adj-neg-00000001"}
    resp = client.post(f"/v1/admin/users/{target['id']}/credit-adjustments", json=body)
    assert resp.status_code == 402


def test_admin_metrics_and_model_update(client, user_with_credits):
    admin = register_user(client)
    make_admin(admin["id"])
    metrics = client.get("/v1/admin/metrics")
    assert metrics.status_code == 200
    assert "usage_by_provider" in metrics.json()

    update = client.patch(
        "/v1/admin/provider-models/mock-music-small",
        json={"credits_per_generation": 2, "reason": "Ajuste de precio de prueba"},
    )
    assert update.status_code == 200 and update.json()["credits_per_generation"] == 2
    client.patch(
        "/v1/admin/provider-models/mock-music-small", json={"credits_per_generation": 1, "reason": "Restaurar precio"}
    )


def test_user_daily_budget_is_enforced(client, user_with_credits, monkeypatch):
    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: None)
    user_with_credits(100)
    settings = get_settings()
    monkeypatch.setattr(settings, "user_daily_credit_limit", 2)
    assert _post(client, key="key-budget-0001").status_code == 201
    assert _post(client, key="key-budget-0002").status_code == 201
    resp = _post(client, key="key-budget-0003")
    assert resp.status_code == 429
    assert resp.json()["detail"]["code"] == "budget_exceeded"


def test_global_daily_budget_is_enforced(client, user_with_credits, monkeypatch):
    from sqlalchemy import func, select

    from app.domain.budget import start_of_day_utc
    from app.models import GenerationJob

    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: None)
    user_with_credits(100)
    settings = get_settings()
    # El presupuesto cuenta todas las generaciones del día (de otros tests también): fijar límite = uso actual + 1.
    with SessionLocal() as db:
        used = db.execute(
            select(func.coalesce(func.sum(GenerationJob.reserved_credits), 0)).where(
                GenerationJob.created_at >= start_of_day_utc()
            )
        ).scalar_one()
    monkeypatch.setattr(settings, "daily_global_credit_budget", int(used) + 1)
    assert _post(client, key="key-global-0001").status_code == 201
    assert _post(client, key="key-global-0002").status_code == 429
