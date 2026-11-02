"""Proveedor simulado: genera un WAV sintético determinista. Sin coste ni red."""

import hashlib
import io
import math
import struct
import uuid
import wave

from app.providers.base import (
    GeneratedAudio,
    GenerationRequest,
    ModelCapabilities,
    MusicProvider,
    ProviderError,
    ProviderStatus,
)

_SAMPLE_RATE = 22050
_MODELS = {
    "mock-music-small": ModelCapabilities(
        model_key="mock-music-small",
        min_duration_s=1,
        max_duration_s=120,
        supports_seed=True,
        supports_negative_prompt=True,
        output_format="wav",
    ),
}


class MockMusicProvider(MusicProvider):
    name = "mock"

    def __init__(self) -> None:
        self._results: dict[str, GeneratedAudio] = {}
        # Los tests inyectan fallos aquí: el siguiente submit() lanza el primero de la lista.
        self.fail_next: list[ProviderError] = []

    def check_available(self) -> None:
        return None

    def capabilities(self, model_key: str) -> ModelCapabilities:
        try:
            return _MODELS[model_key]
        except KeyError as exc:
            raise ProviderError("unknown_model", "Modelo desconocido.", retryable=False) from exc

    def estimate_cost_micros(self, req: GenerationRequest) -> int:
        return 0

    def submit(self, req: GenerationRequest) -> str:
        if self.fail_next:
            raise self.fail_next.pop(0)
        self.validate_capabilities(req)
        ref = f"mock-{uuid.uuid4()}"
        self._results[ref] = _render(req)
        return ref

    def get_status(self, provider_ref: str) -> ProviderStatus:
        return ProviderStatus.COMPLETED if provider_ref in self._results else ProviderStatus.FAILED

    def get_result(self, provider_ref: str) -> GeneratedAudio:
        try:
            return self._results[provider_ref]
        except KeyError as exc:
            raise ProviderError("result_missing", "Resultado no disponible.", retryable=True) from exc

    def classify_error(self, exc: Exception) -> ProviderError:
        if isinstance(exc, ProviderError):
            return exc
        return ProviderError("unexpected", str(exc)[:300], retryable=True)


def _render(req: GenerationRequest) -> GeneratedAudio:
    """Tono mezclado con frecuencias derivadas del prompt y la semilla. Mono, 16 bit."""
    seed_material = f"{req.prompt}|{req.seed}|{req.genre}|{req.mood}".encode()
    digest = hashlib.sha256(seed_material).digest()
    base = 110 + digest[0] % 220
    freqs = [base, base * 1.25, base * 1.5]
    total = req.duration_seconds * _SAMPLE_RATE
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(_SAMPLE_RATE)
        frames = bytearray()
        for i in range(total):
            t = i / _SAMPLE_RATE
            envelope = min(1.0, t * 4, (req.duration_seconds - t) * 4)
            sample = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs)
            frames += struct.pack("<h", int(max(-1.0, min(1.0, sample * envelope * 0.5)) * 32767))
        wav.writeframes(bytes(frames))
    return GeneratedAudio(
        content=buf.getvalue(),
        mime_type="audio/wav",
        extension="wav",
        duration_seconds=float(req.duration_seconds),
    )
