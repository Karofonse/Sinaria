import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.queue import enqueue_job
from app.core.ratelimit import limit_by_user
from app.db.session import get_db
from app.deps import get_current_user, parse_uuid
from app.domain.generations import create_generation, get_job_for_owner
from app.models import GenerationJob, User
from app.schemas import GenerationCreate, GenerationOut

router = APIRouter(prefix="/generations", tags=["generaciones"])
_log = logging.getLogger(__name__)


def to_out(job: GenerationJob) -> GenerationOut:
    return GenerationOut(
        id=job.id,
        status=job.status,
        prompt=job.prompt,
        negative_prompt=job.negative_prompt,
        genre=job.genre,
        mood=job.mood,
        instruments=list(job.instruments or []),
        duration_seconds=job.duration_seconds,
        seed=job.seed,
        reserved_credits=job.reserved_credits,
        model_key=job.model.model_key,
        provider=job.model.provider,
        error_code=job.error_code,
        error_message=job.error_message,
        track_id=job.track.id if job.track else None,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
    )


@router.post(
    "",
    response_model=GenerationOut,
    responses={
        200: {"description": "Solicitud ya registrada con esa clave"},
        201: {"description": "Generación creada"},
    },
    summary="Crear generación (reserva créditos y encola)",
)
def create(
    payload: GenerationCreate,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> GenerationOut:
    limit_by_user("generation", get_settings().rate_limit_generation_per_minute, str(user.id))

    try:
        job, created = create_generation(db, user.id, payload.model_dump(), idempotency_key)
        db.commit()
    except IntegrityError:
        # Otra petición con la misma clave ganó la carrera entre la consulta y el INSERT.
        db.rollback()
        job, created = get_job_for_owner_by_key(db, user.id, idempotency_key), False
    except DomainError:
        db.rollback()
        raise

    if created or job.status == "pending":
        try:
            enqueue_job(job.id)
        except Exception:  # noqa: BLE001 - el reconciliador reencolará los pendientes
            _log.warning("enqueue_failed", extra={"job_id": str(job.id)})

    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return to_out(job)


def get_job_for_owner_by_key(db: Session, user_id: uuid.UUID, key: str) -> GenerationJob:
    job = db.execute(
        select(GenerationJob).where(GenerationJob.user_id == user_id, GenerationJob.idempotency_key == key)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail={"code": "conflict", "message": "Solicitud en curso. Reintenta."}
        )
    return job


@router.get("", response_model=list[GenerationOut], summary="Mis generaciones")
def list_generations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(pending|processing|completed|failed)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[GenerationOut]:
    stmt = select(GenerationJob).where(GenerationJob.user_id == user.id)
    if status_filter:
        stmt = stmt.where(GenerationJob.status == status_filter)
    rows = db.execute(stmt.order_by(GenerationJob.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return [to_out(r) for r in rows]


@router.get("/{job_id}", response_model=GenerationOut, summary="Estado de una generación")
def get_generation(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> GenerationOut:
    job = get_job_for_owner(db, user.id, parse_uuid(job_id))
    return to_out(job)
