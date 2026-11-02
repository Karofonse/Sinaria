"""Adaptador fal.ai — Stable Audio 3 Small (esqueleto DESACTIVADO).

Estado: NO implementado contra la API real. Motivo: en esta sesión no se pudo consultar la
documentación oficial de fal.ai (dominio no permitido). Antes de implementar hay que verificar:
  1. Identificador de endpoint (según búsqueda: fal-ai/stable-audio-3/small/music/text-to-audio).
  2. Nombres y rangos de parámetros, en especial la duración máxima.
  3. Método del SDK oficial vigente (cola submit/status/result) y política de webhooks.
  4. Precio y términos comerciales.
Mientras tanto, cualquier llamada lanza ProviderError permanente. Ver docs/00-analisis-fase0.md.
"""

from app.core.config import get_settings
from app.providers.base import (
    GeneratedAudio,
    GenerationRequest,
    ModelCapabilities,
    MusicProvider,
    ProviderError,
    ProviderStatus,
)

MODEL_KEY = "stable-audio-3-small-music"


class FalStableAudioSmallProvider(MusicProvider):
    name = "fal"

    def check_available(self) -> None:
        settings = get_settings()
        if not settings.fal_enabled:
            raise ProviderError("provider_disabled", "El proveedor fal.ai está desactivado.", retryable=False)
        if not settings.fal_api_key:
            raise ProviderError("provider_not_configured", "Falta FAL_API_KEY.", retryable=False)
        raise ProviderError(
            "not_implemented",
            "Adaptador fal.ai pendiente de verificación contra la documentación oficial.",
            retryable=False,
        )

    def capabilities(self, model_key: str) -> ModelCapabilities:
        raise ProviderError("not_implemented", "Capacidades pendientes de verificación.", retryable=False)

    def estimate_cost_micros(self, req: GenerationRequest) -> int:
        raise ProviderError("not_implemented", "Coste pendiente de verificación.", retryable=False)

    def submit(self, req: GenerationRequest) -> str:
        self.check_available()
        raise AssertionError("unreachable")

    def get_status(self, provider_ref: str) -> ProviderStatus:
        self.check_available()
        raise AssertionError("unreachable")

    def get_result(self, provider_ref: str) -> GeneratedAudio:
        self.check_available()
        raise AssertionError("unreachable")

    def classify_error(self, exc: Exception) -> ProviderError:
        if isinstance(exc, ProviderError):
            return exc
        return ProviderError("unexpected", "Error no clasificado del proveedor fal.", retryable=True)
