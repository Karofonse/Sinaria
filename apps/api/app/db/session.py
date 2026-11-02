from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=10,
    )


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=False)


def SessionLocal() -> Session:  # noqa: N802 - nombre habitual en proyectos FastAPI
    return _session_factory()()


def get_db() -> Iterator[Session]:
    """Dependencia FastAPI: una sesión por petición. El commit lo hace cada caso de uso explícitamente."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_engine_cache() -> None:
    """Usado por tests que cambian DATABASE_URL."""
    _session_factory.cache_clear()
    get_engine.cache_clear()
