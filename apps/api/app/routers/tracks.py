import hashlib
import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import sign_download, verify_download
from app.db.session import get_db
from app.deps import get_current_user, parse_uuid
from app.models import GeneratedTrack, User
from app.schemas import DownloadUrlOut, TrackOut, TrackUpdate
from app.storage.registry import get_storage

router = APIRouter(prefix="/tracks", tags=["biblioteca"])


def _owned_track(db: Session, user: User, track_id: str) -> GeneratedTrack:
    track = db.execute(
        select(GeneratedTrack).where(
            GeneratedTrack.id == parse_uuid(track_id),
            GeneratedTrack.owner_id == user.id,
            GeneratedTrack.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if track is None:
        # Igual que "no existe": no revelar si la pista pertenece a otra cuenta.
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Pista no encontrada."})
    return track


def _to_out(t: GeneratedTrack) -> TrackOut:
    return TrackOut(
        id=t.id,
        title=t.title,
        generation_job_id=t.generation_job_id,
        mime_type=t.mime_type,
        size_bytes=t.size_bytes,
        duration_seconds=t.duration_seconds,
        provider=t.provider,
        model_key=t.model_key,
        created_at=t.created_at,
    )


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


@router.get("", response_model=list[TrackOut], summary="Mi biblioteca")
def list_tracks(
    q: str | None = Query(default=None, max_length=100),
    model_key: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TrackOut]:
    stmt = select(GeneratedTrack).where(GeneratedTrack.owner_id == user.id, GeneratedTrack.deleted_at.is_(None))
    if q and q.strip():
        stmt = stmt.where(func.lower(GeneratedTrack.title).like(f"%{_escape_like(q.strip().lower())}%", escape="\\"))
    if model_key:
        stmt = stmt.where(GeneratedTrack.model_key == model_key)
    rows = db.execute(stmt.order_by(GeneratedTrack.created_at.desc()).limit(limit).offset(offset)).scalars().all()
    return [_to_out(r) for r in rows]


@router.get("/{track_id}", response_model=TrackOut, summary="Detalle de pista con metadatos")
def get_track(track_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> TrackOut:
    return _to_out(_owned_track(db, user, track_id))


@router.patch("/{track_id}", response_model=TrackOut, summary="Renombrar pista")
def rename_track(
    track_id: str, payload: TrackUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> TrackOut:
    track = _owned_track(db, user, track_id)
    track.title = payload.title
    db.commit()
    return _to_out(track)


@router.delete("/{track_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar pista (borrado lógico)")
def delete_track(track_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    track = _owned_track(db, user, track_id)
    track.deleted_at = datetime.now(UTC)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{track_id}/download-url", response_model=DownloadUrlOut, summary="URL firmada de descarga")
def download_url(
    track_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> DownloadUrlOut:
    track = _owned_track(db, user, track_id)
    expires_at = int(time.time()) + get_settings().download_url_ttl_s
    sig = sign_download(track.id, track.owner_id, expires_at)
    return DownloadUrlOut(
        url=f"/v1/tracks/{track.id}/file?expires={expires_at}&sig={sig}",
        expires_at=expires_at,
    )


@router.get("/{track_id}/file", summary="Descarga del archivo (requiere URL firmada vigente)")
def download_file(track_id: str, expires: int, sig: str, db: Session = Depends(get_db)) -> Response:
    track_uuid = parse_uuid(track_id)
    track = db.execute(
        select(GeneratedTrack).where(GeneratedTrack.id == track_uuid, GeneratedTrack.deleted_at.is_(None))
    ).scalar_one_or_none()
    if track is None or not verify_download(track.id, track.owner_id, expires, sig):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Archivo no disponible."}
        )
    content = get_storage().get(track.storage_key)
    if hashlib.sha256(content).hexdigest() != track.sha256:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "integrity_error", "message": "Integridad del archivo fallida."},
        )
    ext = track.mime_type.split("/")[-1]
    return Response(
        content=content,
        media_type=track.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{track.id}.{ext}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
