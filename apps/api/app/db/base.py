from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa. El esquema real lo define Alembic (alembic/versions); estos modelos reflejan ese esquema."""
