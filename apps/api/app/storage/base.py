from abc import ABC, abstractmethod


class ObjectStorage(ABC):
    """Almacenamiento privado. Ningún objeto es público; el acceso es mediante el backend."""

    @abstractmethod
    def put(self, key: str, content: bytes, mime_type: str) -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


def validate_key(key: str) -> str:
    if not key or key.startswith("/") or ".." in key.split("/") or "\\" in key or len(key) > 512:
        raise ValueError("clave de almacenamiento inválida")
    return key
