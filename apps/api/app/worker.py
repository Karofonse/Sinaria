"""Worker de generaciones. Ejecutar: `python -m app.worker`.

Flujo por trabajo:
  1. claim (pending -> processing, condicional: un duplicado no hace nada).
  2. submit al proveedor, guardar su referencia (permite reanudar sin volver a cobrar).
  3. poll hasta completado o timeout.
  4. descargar el resultado y guardarlo en almacenamiento privado propio.
  5. complete (pista + consumo de créditos en una transacción) o fail (liberación).
Errores transitorios se reencolan hasta job_max_attempts; los permanentes fallan y liberan créditos.
"""

import hashlib
import logging
import time
import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import LedgerInvariantError
from app.core.logging import configure_logging
from app.core.queue import dequeue_job, enqueue_job
from app.db.session import SessionLocal
from app.domain import generations as gen
from app.models import GenerationJob, ProviderModel
from app.providers.base import GenerationRequest, ProviderError, ProviderStatus
from app.providers.registry import get_provider
from app.storage.base import ObjectStorage
from app.storage.registry import get_storage

logger = logging.getLogger("sonaria.worker")


def _snapshot(job_id: uuid.UUID) -> dict | None:
    with SessionLocal() as db:
        row = db.execute(
            select(GenerationJob, ProviderModel)
            .join(ProviderModel, ProviderModel.id == GenerationJob.provider_model_id)
            .where(GenerationJob.id == job_id)
        ).one_or_none()
        if row is None:
            return None
        job, model = row
        return {
            "user_id": job.user_id,
            "attempts": job.attempts,
            "provider_job_ref": job.provider_job_ref,
            "provider": model.provider,
            "model_key": model.model_key,
            "request": GenerationRequest(
                model_key=model.model_key,
                prompt=job.prompt,
                negative_prompt=job.negative_prompt,
                genre=job.genre,
                mood=job.mood,
                instruments=tuple(job.instruments or []),
                duration_seconds=job.duration_seconds,
                seed=job.seed,
            ),
        }


def _handle_failure(job_id: uuid.UUID, snap: dict, exc: ProviderError) -> str:
    settings = get_settings()
    with SessionLocal() as db:
        if exc.retryable and snap["attempts"] < settings.job_max_attempts:
            if gen.requeue_job(db, job_id, code=exc.code, message=exc.message):
                enqueue_job(job_id)
                logger.warning(
                    "job_requeued", extra={"job_id": str(job_id), "code": exc.code, "attempt": snap["attempts"]}
                )
                return "requeued"
            return "skipped"
        if gen.fail_job(
            db, job_id, code=exc.code, message=exc.message, provider=snap["provider"], model_key=snap["model_key"]
        ):
            logger.error("job_failed", extra={"job_id": str(job_id), "code": exc.code, "retryable": exc.retryable})
            return "failed"
        return "skipped"


def run_job(job_id: uuid.UUID, *, storage: ObjectStorage | None = None) -> str:
    """Procesa un trabajo. Devuelve el resultado: completed | requeued | failed | skipped."""
    settings = get_settings()
    with SessionLocal() as db:
        if not gen.claim_job(db, job_id):
            return "skipped"
    snap = _snapshot(job_id)
    if snap is None:
        return "skipped"

    provider = get_provider(snap["provider"])
    storage = storage or get_storage()
    try:
        provider.check_available()
        provider.validate_capabilities(snap["request"])
        ref = snap["provider_job_ref"]
        if ref is None:
            ref = provider.submit(snap["request"])
            with SessionLocal() as db:
                gen.record_provider_ref(db, job_id, ref)

        deadline = time.monotonic() + settings.provider_timeout_s
        while True:
            state = provider.get_status(ref)
            if state == ProviderStatus.COMPLETED:
                break
            if state == ProviderStatus.FAILED:
                raise ProviderError("provider_failed", "El proveedor no pudo completar la generación.", retryable=False)
            if time.monotonic() > deadline:
                raise ProviderError("timeout", "Tiempo de espera agotado en el proveedor.", retryable=True)
            time.sleep(settings.provider_poll_interval_s)

        audio = provider.get_result(ref)
        track_id = uuid.uuid4()
        key = f"tracks/{snap['user_id']}/{track_id}.{audio.extension}"
        storage.put(key, audio.content, audio.mime_type)
        sha = hashlib.sha256(audio.content).hexdigest()

        with SessionLocal() as db:
            ok = gen.complete_job(
                db,
                job_id,
                track_id=track_id,
                storage_key=key,
                mime_type=audio.mime_type,
                size_bytes=len(audio.content),
                duration_seconds=audio.duration_seconds,
                sha256=sha,
                provider=snap["provider"],
                model_key=snap["model_key"],
                estimated_cost_micros=provider.estimate_cost_micros(snap["request"]),
            )
        if not ok:
            storage.delete(key)  # el trabajo cambió de estado mientras se generaba: no dejar huérfanos
            return "skipped"
        logger.info("job_completed", extra={"job_id": str(job_id)})
        return "completed"
    except ProviderError as exc:
        return _handle_failure(job_id, snap, exc)
    except LedgerInvariantError as exc:
        # Un fallo de invariante no debe reintentarse a ciegas: se marca para revisión manual.
        logger.critical("ledger_invariant", extra={"job_id": str(job_id), "detail": str(exc)})
        return _handle_failure(job_id, snap, ProviderError("ledger_invariant", str(exc), retryable=False))
    except Exception as exc:  # noqa: BLE001
        classified = provider.classify_error(exc)
        logger.exception("job_unexpected_error", extra={"job_id": str(job_id)})
        return _handle_failure(job_id, snap, classified)


def reconcile(stuck_after_s: int | None = None) -> dict[str, int]:
    """Reencola pendientes olvidados y recupera trabajos estancados en processing."""
    settings = get_settings()
    stuck_after = stuck_after_s or settings.job_stuck_after_s
    counts = {"requeued_pending": 0, "recovered_processing": 0, "failed_processing": 0}
    with SessionLocal() as db:
        pending, processing = gen.find_stuck_jobs(db, stuck_after_s=stuck_after)
    for job_id in pending:
        enqueue_job(job_id)
        counts["requeued_pending"] += 1
    for job_id in processing:
        snap = _snapshot(job_id)
        if snap is None:
            continue
        exc = ProviderError("stuck_processing", "Trabajo sin actividad; recuperado por reconciliación.", retryable=True)
        if snap["attempts"] < settings.job_max_attempts:
            with SessionLocal() as db:
                if gen.requeue_job(db, job_id, code=exc.code, message=exc.message):
                    enqueue_job(job_id)
                    counts["recovered_processing"] += 1
        else:
            if _handle_failure(job_id, snap, ProviderError(exc.code, exc.message, retryable=False)) == "failed":
                counts["failed_processing"] += 1
    return counts


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("worker_started", extra={"queue": settings.queue_name})
    last_reconcile = 0.0
    while True:
        if time.monotonic() - last_reconcile > 60:
            try:
                reconcile()
            except Exception:  # noqa: BLE001
                logger.exception("reconcile_failed")
            last_reconcile = time.monotonic()
        job_id = dequeue_job(timeout_s=5)
        if job_id is None:
            continue
        try:
            run_job(job_id)
        except Exception:  # noqa: BLE001 - el worker nunca debe caer por un trabajo
            logger.exception("worker_loop_error", extra={"job_id": str(job_id)})


if __name__ == "__main__":
    main()
