from functools import lru_cache

from app.core.config import get_settings
from app.storage.base import ObjectStorage
from app.storage.local import LocalObjectStorage


@lru_cache
def get_storage() -> ObjectStorage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        from app.storage.s3 import S3ObjectStorage

        return S3ObjectStorage()
    return LocalObjectStorage(settings.storage_local_dir)
