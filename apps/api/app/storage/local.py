from pathlib import Path

from app.storage.base import ObjectStorage, validate_key


class LocalObjectStorage(ObjectStorage):
    """Disco local. Solo para desarrollo y tests; en sandbox/prod se usa R2/S3."""

    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / validate_key(key)).resolve()
        if self.root not in path.parents:
            raise ValueError("clave fuera del directorio de almacenamiento")
        return path

    def put(self, key: str, content: bytes, mime_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(content)
        tmp.replace(path)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()
