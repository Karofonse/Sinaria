"""Ciclo de vida de los trabajos de generación.

Transiciones permitidas (todas condicionales en SQL, así dos workers no pueden hacer lo mismo):
    pending    -> processing  (claim_job)
    processing -> pending     (requeue_job: reintento transitorio)
    processing -> completed   (complete_job: consume créditos y guarda la pista)
    pending|processing -> failed (fail_job: libera créditos)
"""

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationProblem
from app.domain import budget, credits
from app.models import GeneratedTrack, GenerationJob, ProviderModel, ProviderUsage

logger = logging.getLogger(__name__)


def fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_generation(
    db: Session,
    user_id: uuid.UUID,
    payload: dict[str, Any],
    idempotency_key: str,
) -> tuple[GenerationJob, bool]:
    """Crea un trabajo y reserva créditos en la transacción del llamador.

    Devuelve (job, creado). Si la clave de idempotencia ya existe con la misma solicitud,
    devuelve el trabajo existente sin cobrar de nuevo.
    """
    fp = fingerprint(payload)
    existing = db.execute(
        select(GenerationJob).where(GenerationJob.user_id == user_id, GenerationJob.idempotency_key == idempotency_key)
    ).scalar_one_or_none()
    if existing is not None:
        if existing.request_fingerprint != fp:
            raise ConflictError("La clave de idempotencia ya se usó con una solicitud distinta.")
        return existing, False

    model = db.execute(
        select(ProviderModel).where(ProviderModel.model_key == payload["model_key"], ProviderModel.enabled.is_(True))
    ).scalar_one_or_none()
    if model is None:
        raise NotFoundError("El modelo solicitado no está disponible.")

    duration = payload["duration_seconds"]
    if not (model.min_duration_s <= duration <= model.max_duration_s):
        raise ValidationProblem(
            f"La duración debe estar entre {model.min_duration_s} y {model.max_duration_s} segundos."
        )
    if payload.get("seed") is not None and not model.supports_seed:
        raise ValidationProblem("Este modelo no admite semilla.")
    if payload.get("negative_prompt") and not model.supports_negative_prompt:
        raise ValidationProblem("Este modelo no admite prompt negativo.")

    cost = model.credits_per_generation
    budget.assert_within_budget(db, user_id, cost)

    job = GenerationJob(
        id=uuid.uuid4(),
        user_id=user_id,
        provider_model_id=model.id,
        idempotency_key=idempotency_key,
        request_fingerprint=fp,
        status="pending",
        prompt=payload["prompt"],
        negative_prompt=payload.get("negative_prompt"),
        genre=payload.get("genre"),
        mood=payload.get("mood"),
        instruments=list(payload.get("instruments") or []),
        duration_seconds=duration,
        seed=payload.get("seed"),
        reserved_credits=cost,
        attempts=0,
    )
    db.add(job)
    db.flush()
    credits.reserve(db, user_id, cost, job.id)  # InsufficientCredits si no hay saldo
    return job, True


def get_job_for_owner(db: Session, user_id: uuid.UUID, job_id: uuid.UUID) -> GenerationJob:
    job = db.execute(
        select(GenerationJob).where(GenerationJob.id == job_id, GenerationJob.user_id == user_id)
    ).scalar_one_or_none()
    if job is None:
        raise NotFoundError("Generación no encontrada.")
    return job


# ----------------------------------------------------------------------------- transiciones (worker)


def claim_job(db: Session, job_id: uuid.UUID) -> bool:
    result = db.execute(
        update(GenerationJob)
        .where(GenerationJob.id == job_id, GenerationJob.status == "pending")
        .values(status="processing", attempts=GenerationJob.attempts + 1, updated_at=func.now())
    )
    db.commit()
    return result.rowcount == 1


def record_provider_ref(db: Session, job_id: uuid.UUID, provider_ref: str) -> None:
    db.execute(
        update(GenerationJob)
        .where(
            GenerationJob.id == job_id, GenerationJob.status == "processing", GenerationJob.provider_job_ref.is_(None)
        )
        .values(provider_job_ref=provider_ref, updated_at=func.now())
    )
    db.commit()


def complete_job(
    db: Session,
    job_id: uuid.UUID,
    *,
    track_id: uuid.UUID,
    storage_key: str,
    mime_type: str,
    size_bytes: int,
    duration_seconds: float,
    sha256: str,
    provider: str,
    model_key: str,
    estimated_cost_micros: int,
) -> bool:
    job = db.execute(select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()).scalar_one_or_none()
    if job is None or job.status != "processing":
        db.rollback()
        return False

    title_source = job.genre or "Sin género"
    title = f"{title_source} · {job.prompt[:60]}".strip()
    db.add(
        GeneratedTrack(
            id=track_id,
            owner_id=job.user_id,
            generation_job_id=job.id,
            title=title[:200],
            storage_key=storage_key,
            mime_type=mime_type,
            size_bytes=size_bytes,
            duration_seconds=duration_seconds,
            sha256=sha256,
            provider=provider,
            model_key=model_key,
        )
    )
    now = datetime.now(UTC)
    job.status = "completed"
    job.completed_at = now
    job.error_code = None
    job.error_message = None
    credits.consume(db, job.user_id, job.reserved_credits, job.id)
    db.add(
        ProviderUsage(
            provider=provider,
            model_key=model_key,
            user_id=job.user_id,
            generation_job_id=job.id,
            outcome="completed",
            credits_charged=job.reserved_credits,
            estimated_cost_micros=estimated_cost_micros,
        )
    )
    db.commit()
    return True


def fail_job(db: Session, job_id: uuid.UUID, *, code: str, message: str, provider: str, model_key: str) -> bool:
    job = db.execute(select(GenerationJob).where(GenerationJob.id == job_id).with_for_update()).scalar_one_or_none()
    if job is None or job.status not in ("pending", "processing"):
        db.rollback()
        return False

    job.status = "failed"
    job.error_code = code[:64]
    job.error_message = message[:2000]
    job.completed_at = datetime.now(UTC)
    credits.release(db, job.user_id, job.reserved_credits, job.id)
    db.add(
        ProviderUsage(
            provider=provider,
            model_key=model_key,
            user_id=job.user_id,
            generation_job_id=job.id,
            outcome="failed",
            credits_charged=0,
        )
    )
    db.commit()
    return True


def requeue_job(db: Session, job_id: uuid.UUID, *, code: str, message: str) -> bool:
    result = db.execute(
        update(GenerationJob)
        .where(GenerationJob.id == job_id, GenerationJob.status == "processing")
        .values(status="pending", error_code=code[:64], error_message=message[:2000], updated_at=func.now())
    )
    db.commit()
    return result.rowcount == 1


def find_stuck_jobs(db: Session, *, stuck_after_s: int) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """Devuelve (ids pendientes sin actividad para reencolar, ids en processing demasiado tiempo)."""
    now = datetime.now(UTC)
    pending_cutoff = now - timedelta(seconds=60)
    processing_cutoff = now - timedelta(seconds=stuck_after_s)
    pending = (
        db.execute(
            select(GenerationJob.id).where(GenerationJob.status == "pending", GenerationJob.updated_at < pending_cutoff)
        )
        .scalars()
        .all()
    )
    processing = (
        db.execute(
            select(GenerationJob.id).where(
                GenerationJob.status == "processing", GenerationJob.updated_at < processing_cutoff
            )
        )
        .scalars()
        .all()
    )
    return list(pending), list(processing)


__all__ = [
    "claim_job",
    "complete_job",
    "create_generation",
    "fail_job",
    "find_stuck_jobs",
    "fingerprint",
    "get_job_for_owner",
    "record_provider_ref",
    "requeue_job",
]
