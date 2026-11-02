import uuid

from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.models import GeneratedTrack, GenerationJob
from app.providers.base import ProviderError
from app.providers.registry import get_provider
from app.storage.registry import get_storage
from app.worker import reconcile, run_job
from tests.conftest import register_user

PAYLOAD = {
    "model_key": "mock-music-small",
    "prompt": "Pista ambiental con pads cálidos y piano suave",
    "negative_prompt": None,
    "genre": "ambient",
    "mood": "calm",
    "instruments": ["piano", "pads"],
    "duration_seconds": 2,
    "seed": 7,
}


def _post(client, payload=None, key="key-generation-001"):
    return client.post("/v1/generations", json=payload or PAYLOAD, headers={"Idempotency-Key": key})


def _balance(user_id):
    with SessionLocal() as db:
        return db.execute(
            text("SELECT available_credits, reserved_credits FROM wallets WHERE user_id = :u"), {"u": user_id}
        ).one()


def _job(job_id):
    with SessionLocal() as db:
        return db.execute(select(GenerationJob).where(GenerationJob.id == uuid.UUID(job_id))).scalar_one()


def test_requires_idempotency_key(client, user_with_credits):
    user_with_credits(5)
    resp = client.post("/v1/generations", json=PAYLOAD)
    assert resp.status_code == 422


def test_rejects_without_credits_and_reserves_nothing(client):
    info = register_user(client)
    resp = _post(client, key="key-no-credits-01")
    assert resp.status_code == 402
    assert resp.json()["detail"]["code"] == "insufficient_credits"
    assert _balance(info["id"]) == (0, 0)


def test_creates_job_reserves_credits_and_is_idempotent(client, user_with_credits, monkeypatch):
    enqueued = []
    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: enqueued.append(job_id))
    info = user_with_credits(10)

    first = _post(client, key="key-idem-000001")
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["status"] == "pending" and body["reserved_credits"] == 1
    assert _balance(info["id"]) == (9, 1)

    replay = _post(client, key="key-idem-000001")
    assert replay.status_code == 200
    assert replay.json()["id"] == body["id"]
    assert _balance(info["id"]) == (9, 1), "un reintento no debe reservar de nuevo"
    # El primer intento encola; el reintento sobre un job aún pendiente reencola de forma segura
    # (el claim condicional del worker impide ejecutarlo dos veces).
    assert len(enqueued) == 2


def test_same_key_different_payload_conflicts(client, user_with_credits, monkeypatch):
    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: None)
    user_with_credits(10)
    assert _post(client, key="key-conflict-01").status_code == 201
    other = {**PAYLOAD, "prompt": "Otra descripción completamente distinta"}
    assert _post(client, other, key="key-conflict-01").status_code == 409


def test_validation_rejects_out_of_range_duration_and_unknown_fields(client, user_with_credits):
    user_with_credits(10)
    assert _post(client, {**PAYLOAD, "duration_seconds": 0}, key="key-dur-zero-1").status_code == 422
    assert _post(client, {**PAYLOAD, "duration_seconds": 9999}, key="key-dur-big-1").status_code == 422
    assert _post(client, {**PAYLOAD, "instrumental": False}, key="key-instr-no-1").status_code == 422
    assert _post(client, {**PAYLOAD, "balance": 9999}, key="key-extra-field1").status_code == 422


def test_model_duration_limit_is_enforced_by_server(client, user_with_credits, monkeypatch):
    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: None)
    user_with_credits(10)
    resp = _post(client, {**PAYLOAD, "duration_seconds": 500}, key="key-maxdur-001")
    assert resp.status_code == 422 and "120" in resp.text


def test_disabled_model_is_not_available(client, user_with_credits, monkeypatch):
    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: None)
    user_with_credits(10)
    resp = _post(client, {**PAYLOAD, "model_key": "stable-audio-3-small-music"}, key="key-disabled-1")
    assert resp.status_code == 404


def test_worker_completes_job_stores_private_file_and_consumes_credits(client, user_with_credits, monkeypatch):
    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: None)
    info = user_with_credits(5)
    job_id = _post(client, key="key-worker-ok-1").json()["id"]

    assert run_job(uuid.UUID(job_id)) == "completed"

    job = _job(job_id)
    assert job.status == "completed" and job.completed_at is not None
    assert _balance(info["id"]) == (4, 0)
    with SessionLocal() as db:
        track = db.execute(select(GeneratedTrack).where(GeneratedTrack.generation_job_id == job.id)).scalar_one()
        assert track.owner_id == uuid.UUID(info["id"])
        assert track.mime_type == "audio/wav" and track.size_bytes > 1000
    content = get_storage().get(track.storage_key)
    assert content[:4] == b"RIFF", "el archivo guardado debe ser WAV válido"


def test_running_same_job_twice_does_not_double_consume(client, user_with_credits, monkeypatch):
    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: None)
    info = user_with_credits(5)
    job_id = uuid.UUID(_post(client, key="key-double-run-1").json()["id"])
    assert run_job(job_id) == "completed"
    assert run_job(job_id) == "skipped"
    assert _balance(info["id"]) == (4, 0)


def test_permanent_provider_failure_releases_credits(client, user_with_credits, monkeypatch):
    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: None)
    info = user_with_credits(5)
    job_id = uuid.UUID(_post(client, key="key-perm-fail-1").json()["id"])
    provider = get_provider("mock")
    provider.fail_next.append(ProviderError("content_rejected", "Prompt rechazado.", retryable=False))
    assert run_job(job_id) == "failed"

    job = _job(str(job_id))
    assert job.status == "failed" and job.error_code == "content_rejected"
    assert _balance(info["id"]) == (5, 0), "los créditos reservados deben liberarse"


def test_transient_failure_is_retried_then_completes(client, user_with_credits, monkeypatch):
    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: None)
    monkeypatch.setattr("app.worker.enqueue_job", lambda job_id: None)
    info = user_with_credits(5)
    job_id = uuid.UUID(_post(client, key="key-transient-1").json()["id"])
    get_provider("mock").fail_next.append(ProviderError("rate_limited", "429", retryable=True))

    assert run_job(job_id) == "requeued"
    assert _job(str(job_id)).status == "pending"
    assert _balance(info["id"]) == (4, 1), "durante el reintento los créditos siguen reservados"

    assert run_job(job_id) == "completed"
    assert _balance(info["id"]) == (4, 0)


def test_retries_are_bounded_then_release(client, user_with_credits, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: None)
    monkeypatch.setattr("app.worker.enqueue_job", lambda job_id: None)
    info = user_with_credits(5)
    job_id = uuid.UUID(_post(client, key="key-bounded-01").json()["id"])
    provider = get_provider("mock")
    for _ in range(get_settings().job_max_attempts + 1):
        provider.fail_next.append(ProviderError("unavailable", "503", retryable=True))
    outcome = None
    for _ in range(get_settings().job_max_attempts + 1):
        outcome = run_job(job_id)
        if outcome == "failed":
            break
    assert outcome == "failed"
    assert _balance(info["id"]) == (5, 0)


def test_reconciler_recovers_stuck_processing_job(client, user_with_credits, monkeypatch):
    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: None)
    monkeypatch.setattr("app.worker.enqueue_job", lambda job_id: None)
    info = user_with_credits(5)
    job_id = uuid.UUID(_post(client, key="key-stuck-0001").json()["id"])
    with SessionLocal() as db:
        db.execute(
            text(
                "UPDATE generation_jobs SET status='processing', attempts=1, updated_at = now() - interval '2 hours' WHERE id=:i"
            ),
            {"i": job_id},
        )
        db.commit()
    counts = reconcile(stuck_after_s=60)
    assert counts["recovered_processing"] == 1
    assert _job(str(job_id)).status == "pending"
    assert run_job(job_id) == "completed"
    assert _balance(info["id"]) == (4, 0)


def test_user_cannot_read_another_users_generation(client, user_with_credits, monkeypatch):
    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: None)
    user_with_credits(5)
    job_id = _post(client, key="key-owner-ge-01").json()["id"]
    client.cookies.clear()
    register_user(client)  # otro usuario distinto
    assert client.get(f"/v1/generations/{job_id}").status_code == 404


def test_list_generations_only_returns_own_jobs(client, user_with_credits, monkeypatch):
    monkeypatch.setattr("app.routers.generations.enqueue_job", lambda job_id: None)
    user_with_credits(5)
    _post(client, key="key-list-own-01")
    client.cookies.clear()
    register_user(client)
    assert client.get("/v1/generations").json() == []
