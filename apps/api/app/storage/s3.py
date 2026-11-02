from app.storage.base import ObjectStorage


class S3ObjectStorage(ObjectStorage):
    """Cloudflare R2 / S3 compatible. PENDIENTE: requiere bucket privado y credenciales del propietario.

    Implementación prevista: boto3 con endpoint de R2, bucket sin acceso público, sin ACL pública,
    y lectura solo desde el backend o worker.
    """

    def __init__(self, *_: object, **__: object):
        raise NotImplementedError("Almacenamiento S3/R2 pendiente: falta bucket y credenciales.")

    def put(self, key: str, content: bytes, mime_type: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def get(self, key: str) -> bytes:  # pragma: no cover
        raise NotImplementedError

    def delete(self, key: str) -> None:  # pragma: no cover
        raise NotImplementedError
