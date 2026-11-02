"""Contrato de los proveedores musicales. Ningún código de dominio importa SDKs de proveedor."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class ProviderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProviderError(Exception):
    """Error clasificado. `retryable` decide si el worker reintenta."""

    def __init__(self, code: str, message: str, *, retryable: bool):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class GenerationRequest:
    model_key: str
    prompt: str
    negative_prompt: str | None
    genre: str | None
    mood: str | None
    instruments: tuple[str, ...] = field(default_factory=tuple)
    duration_seconds: int = 30
    seed: int | None = None


@dataclass(frozen=True)
class ModelCapabilities:
    model_key: str
    min_duration_s: int
    max_duration_s: int
    supports_seed: bool
    supports_negative_prompt: bool
    output_format: str


@dataclass(frozen=True)
class GeneratedAudio:
    content: bytes
    mime_type: str
    extension: str
    duration_seconds: float


class MusicProvider(ABC):
    name: str

    @abstractmethod
    def check_available(self) -> None:
        """Lanza ProviderError(permanent) si el proveedor está desactivado o sin credenciales."""

    @abstractmethod
    def capabilities(self, model_key: str) -> ModelCapabilities:
        """Capacidades del modelo. Lanza ProviderError si el modelo no existe en este proveedor."""

    def validate_capabilities(self, req: GenerationRequest) -> None:
        caps = self.capabilities(req.model_key)
        if not (caps.min_duration_s <= req.duration_seconds <= caps.max_duration_s):
            raise ProviderError(
                "unsupported_duration",
                f"La duración debe estar entre {caps.min_duration_s} y {caps.max_duration_s} segundos.",
                retryable=False,
            )
        if req.seed is not None and not caps.supports_seed:
            raise ProviderError("unsupported_seed", "Este modelo no admite semilla.", retryable=False)
        if req.negative_prompt and not caps.supports_negative_prompt:
            raise ProviderError(
                "unsupported_negative_prompt", "Este modelo no admite prompt negativo.", retryable=False
            )

    @abstractmethod
    def estimate_cost_micros(self, req: GenerationRequest) -> int:
        """Coste estimado para el proveedor en micro-unidades de moneda (solo para reportes y presupuesto)."""

    @abstractmethod
    def submit(self, req: GenerationRequest) -> str:
        """Envía la generación y devuelve una referencia de trabajo del proveedor."""

    @abstractmethod
    def get_status(self, provider_ref: str) -> ProviderStatus:
        """Estado actual del trabajo remoto."""

    @abstractmethod
    def get_result(self, provider_ref: str) -> GeneratedAudio:
        """Descarga el resultado. Las URL temporales del proveedor se usan aquí y no se guardan."""

    @abstractmethod
    def classify_error(self, exc: Exception) -> ProviderError:
        """Traduce excepciones del SDK/HTTP a ProviderError con política de reintento."""
