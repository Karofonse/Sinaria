"""Registro de adaptadores. Añadir un proveedor = nueva clase + una línea aquí + fila en provider_models."""

from functools import lru_cache

from app.providers.base import MusicProvider, ProviderError
from app.providers.fal import FalStableAudioSmallProvider
from app.providers.mock import MockMusicProvider
from app.providers.stability import StabilityStableAudioProvider


@lru_cache
def _all() -> dict[str, MusicProvider]:
    return {
        "mock": MockMusicProvider(),
        "fal": FalStableAudioSmallProvider(),
        "stability": StabilityStableAudioProvider(),
    }


def get_provider(name: str) -> MusicProvider:
    try:
        return _all()[name]
    except KeyError as exc:
        raise ProviderError("unknown_provider", f"Proveedor desconocido: {name}", retryable=False) from exc
