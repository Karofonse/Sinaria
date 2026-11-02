"""Pruebas del libro mayor directamente contra PostgreSQL: idempotencia, CHECKs e inmutabilidad."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.errors import InsufficientCredits
from app.db.session import SessionLocal
from app.domain import credits
from tests.conftest import register_user


@pytest.fixture()
def wallet_user(client):
    info = register_user(client)
    return uuid.UUID(info["id"])


def _balance(uid):
    with SessionLocal() as db:
        return credits.get_balance(db, uid)


def test_grant_is_idempotent(wallet_user):
    key = f"pay:{uuid.uuid4()}"
    with SessionLocal() as db:
        assert credits.grant_purchase(db, wallet_user, 30, key, "pay-1") is True
        db.commit()
    with SessionLocal() as db:
        assert credits.grant_purchase(db, wallet_user, 30, key, "pay-1") is False
        db.commit()
    assert _balance(wallet_user) == (30, 0)


def test_reserve_consume_and_release_flow(wallet_user):
    with SessionLocal() as db:
        credits.grant_purchase(db, wallet_user, 10, f"g:{uuid.uuid4()}", "x")
        db.commit()
    job_ok, job_fail = uuid.uuid4(), uuid.uuid4()
    with SessionLocal() as db:
        assert credits.reserve(db, wallet_user, 4, job_ok)
        assert credits.reserve(db, wallet_user, 3, job_fail)
        db.commit()
    assert _balance(wallet_user) == (3, 7)
    with SessionLocal() as db:
        assert credits.consume(db, wallet_user, 4, job_ok)
        assert credits.release(db, wallet_user, 3, job_fail)
        db.commit()
    # 10 comprados - 4 consumidos = 6 disponibles; la liberación devuelve 3 (ya incluidos) y no hay reservas.
    assert _balance(wallet_user) == (6, 0)


def test_replayed_reserve_does_not_double_charge(wallet_user):
    with SessionLocal() as db:
        credits.grant_purchase(db, wallet_user, 5, f"g:{uuid.uuid4()}", "x")
        db.commit()
    job = uuid.uuid4()
    for _ in range(3):
        with SessionLocal() as db:
            credits.reserve(db, wallet_user, 2, job)
            db.commit()
    assert _balance(wallet_user) == (3, 2)


def test_insufficient_credits_never_go_negative(wallet_user):
    with SessionLocal() as db:
        with pytest.raises(InsufficientCredits):
            credits.reserve(db, wallet_user, 1, uuid.uuid4())
        db.rollback()
    assert _balance(wallet_user) == (0, 0)


def test_database_rejects_negative_balance_even_if_app_is_buggy(wallet_user):
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
        with pytest.raises(DBAPIError):
            db.execute(text("UPDATE wallets SET available_credits = -1 WHERE user_id = :u"), {"u": wallet_user})
        db.rollback()


def test_ledger_rows_are_immutable(wallet_user):
    with SessionLocal() as db:
        credits.grant_purchase(db, wallet_user, 2, f"g:{uuid.uuid4()}", "x")
        db.commit()
    with SessionLocal() as db:
        with pytest.raises(DBAPIError, match="append-only"):
            db.execute(text("UPDATE credit_transactions SET available_delta = 999999"))
        db.rollback()
    with SessionLocal() as db:
        with pytest.raises(DBAPIError, match="append-only"):
            db.execute(text("DELETE FROM credit_transactions"))
        db.rollback()


def test_database_rejects_malformed_movement(wallet_user):
    with SessionLocal() as db:
        credits.grant_purchase(db, wallet_user, 1, f"g:{uuid.uuid4()}", "x")
        db.commit()
    with SessionLocal() as db:
        wallet_id = db.execute(text("SELECT id FROM wallets WHERE user_id = :u"), {"u": wallet_user}).scalar_one()
        # "consume" que además toca available: la BD debe rechazarlo aunque el código Python no lo permita.
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "INSERT INTO credit_transactions (id, wallet_id, kind, available_delta, reserved_delta, idempotency_key) "
                    "VALUES (:id, :w, 'consume', 5, -5, :k)"
                ),
                {"id": uuid.uuid4(), "w": wallet_id, "k": f"bad:{uuid.uuid4()}"},
            )
        db.rollback()


def test_adjustment_requires_reason_in_database(wallet_user):
    with SessionLocal() as db:
        credits.grant_purchase(db, wallet_user, 1, f"g:{uuid.uuid4()}", "x")
        db.commit()
    with SessionLocal() as db:
        wallet_id = db.execute(text("SELECT id FROM wallets WHERE user_id = :u"), {"u": wallet_user}).scalar_one()
        with pytest.raises(IntegrityError):
            db.execute(
                text(
                    "INSERT INTO credit_transactions (id, wallet_id, kind, available_delta, reserved_delta, idempotency_key) "
                    "VALUES (:id, :w, 'adjustment', 5, 0, :k)"
                ),
                {"id": uuid.uuid4(), "w": wallet_id, "k": f"adj:{uuid.uuid4()}"},
            )
        db.rollback()


def test_concurrent_reserves_never_overspend(wallet_user):
    """20 hilos intentan reservar 1 crédito cada uno con 10 créditos: exactamente 10 deben tener éxito."""
    with SessionLocal() as db:
        credits.grant_purchase(db, wallet_user, 10, f"g:{uuid.uuid4()}", "x")
        db.commit()

    def attempt(_: int) -> bool:
        with SessionLocal() as db:
            try:
                ok = credits.reserve(db, wallet_user, 1, uuid.uuid4())
                db.commit()
                return ok
            except InsufficientCredits:
                db.rollback()
                return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(attempt, range(20)))
    assert sum(results) == 10
    assert _balance(wallet_user) == (0, 10)


def test_concurrent_duplicate_grants_apply_once(wallet_user):
    key = f"pay:{uuid.uuid4()}"

    def attempt(_: int) -> bool:
        with SessionLocal() as db:
            try:
                applied = credits.grant_purchase(db, wallet_user, 50, key, "pay-dup")
                db.commit()
                return applied
            except IntegrityError:
                db.rollback()
                return False

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(attempt, range(12)))
    assert results.count(True) == 1
    assert _balance(wallet_user) == (50, 0)


def test_ledger_reconciles_with_wallet_snapshot(wallet_user):
    """Invariante: el saldo de la billetera es igual a la suma de deltas del libro mayor."""
    with SessionLocal() as db:
        credits.grant_purchase(db, wallet_user, 20, f"g:{uuid.uuid4()}", "x")
        credits.reserve(db, wallet_user, 6, uuid.uuid4())
        credits.reserve(db, wallet_user, 2, uuid.uuid4())
        db.commit()
    with SessionLocal() as db:
        row = db.execute(
            text(
                "SELECT w.available_credits, w.reserved_credits, "
                "COALESCE(SUM(t.available_delta),0), COALESCE(SUM(t.reserved_delta),0) "
                "FROM wallets w LEFT JOIN credit_transactions t ON t.wallet_id = w.id "
                "WHERE w.user_id = :u GROUP BY w.id"
            ),
            {"u": wallet_user},
        ).one()
    assert row[0] == row[2] and row[1] == row[3]
