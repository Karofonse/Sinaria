"""Adaptador Stability AI — Stable Audio 3.0 (preparado, NO implementado).

Bloqueado hasta: tarifa oficial confirmada (fuentes de terceros se contradicen: 8 vs 26 créditos)
y revisión de licencia comercial por el propietario. Ver docs/00-analisis-fase0.md §2.2.
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


class StabilityStableAudioProvider(MusicProvider):
    name = "stability"

    def check_available(self) -> None:
        settings = get_settings()
        if not settings.stability_enabled:
            raise ProviderError("provider_disabled", "El proveedor Stability AI está desactivado.", retryable=False)
        if not settings.stability_api_key:
            raise ProviderError("provider_not_configured", "Falta STABILITY_API_KEY.", retryable=False)
        raise ProviderError(
            "not_implemented",
            "Adaptador Stability AI pendiente de tarifa y licencia verificadas.",
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
        return ProviderError("unexpected", "Error no clasificado del proveedor Stability.", retryable=True)
