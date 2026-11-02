"""Configuración de pruebas. Usa PostgreSQL y Redis reales (no mocks de BD): los triggers y CHECKs
de la migración son parte de lo que se verifica."""

import os
import uuid
from pathlib import Path

_TMP = Path(os.environ.get("SONARIA_TEST_TMP", "/tmp/sonaria-tests")).resolve()
os.environ.setdefault("APP_ENV", "test")
# Las pruebas BORRAN el esquema. Nunca heredan DATABASE_URL del entorno: usan una URL de test explícita
# y se niegan a arrancar si la base no se llama *_test.
_TEST_DATABASE_URL = os.environ.get(
    "SONARIA_TEST_DATABASE_URL", "postgresql+psycopg://sonaria:sonaria_dev@127.0.0.1:5432/sonaria_test"
)
if not _TEST_DATABASE_URL.rsplit("/", 1)[-1].endswith("_test"):
    raise SystemExit("SONARIA_TEST_DATABASE_URL debe apuntar a una base cuyo nombre termine en _test")
os.environ["DATABASE_URL"] = _TEST_DATABASE_URL
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/1")
os.environ["QUEUE_NAME"] = "sonaria:test-jobs"
os.environ["STORAGE_LOCAL_DIR"] = str(_TMP / "storage")
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["PROVIDER_POLL_INTERVAL_S"] = "0.01"
os.environ["DAILY_GLOBAL_CREDIT_BUDGET"] = "1000000"
os.environ["USER_DAILY_CREDIT_LIMIT"] = "1000"

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()
API_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    from app.db.session import get_engine, reset_engine_cache
    from app.seed import seed_reference_data

    reset_engine_cache()
    with get_engine().begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(cfg, "head")
    seed_reference_data()
    yield


@pytest.fixture(autouse=True)
def _reset_mock_provider():
    from app.providers.registry import get_provider

    get_provider("mock").fail_next.clear()
    yield
    get_provider("mock").fail_next.clear()


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def new_email() -> str:
    return f"user-{uuid.uuid4().hex[:10]}@example.com"


def register_user(client: TestClient, email: str | None = None, password: str = "contraseña-segura-123") -> dict:
    email = email or new_email()
    resp = client.post(
        "/v1/auth/register",
        json={"email": email, "password": password, "display_name": "Test User", "locale": "es"},
    )
    assert resp.status_code == 201, resp.text
    return {"email": email, "password": password, "id": resp.json()["id"]}


def make_admin(user_id: str) -> None:
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        db.execute(
            text(
                "INSERT INTO user_roles (user_id, role_id) "
                "SELECT :uid, id FROM roles WHERE name = 'admin' ON CONFLICT DO NOTHING"
            ),
            {"uid": user_id},
        )
        db.commit()


def grant_credits(user_id: str, credits: int) -> None:
    from app.db.session import SessionLocal
    from app.domain import credits as ledger

    if credits <= 0:  # la BD rechaza compras de 0: sin créditos no hay movimiento
        return
    with SessionLocal() as db:
        ledger.grant_purchase(db, uuid.UUID(user_id), credits, f"test-grant:{uuid.uuid4()}", "test")
        db.commit()


@pytest.fixture()
def user_with_credits(client):
    def _make(credits: int = 50) -> dict:
        info = register_user(client)
        grant_credits(info["id"], credits)
        return info

    return _make
