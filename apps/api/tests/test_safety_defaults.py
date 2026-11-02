"""Garantías de seguridad por defecto: nada costoso ni financiero se activa sin autorización explícita."""

import pytest

from app.core.config import get_settings
from app.core.errors import ConflictError  # noqa: F401 - comprueba que el módulo de errores carga
from app.providers.base import ProviderError
from app.providers.registry import get_provider
from tests.conftest import register_user


def test_real_providers_are_disabled_by_default():
    settings = get_settings()
    assert settings.fal_enabled is False
    assert settings.stability_enabled is False
    assert settings.payments_enabled is False
    assert settings.default_provider == "mock"


@pytest.mark.parametrize("name", ["fal", "stability"])
def test_real_provider_refuses_to_call_network_when_disabled(name):
    provider = get_provider(name)
    with pytest.raises(ProviderError) as exc:
        provider.check_available()
    assert exc.value.code == "provider_disabled"
    assert exc.value.retryable is False


def test_checkout_is_refused_while_payments_disabled(client):
    register_user(client)
    resp = client.post("/v1/billing/checkout")
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "payments_disabled"


def test_packages_seeded_inactive_are_not_for_sale(client):
    register_user(client)
    assert client.get("/v1/catalog/packages").json() == []


def test_rate_limit_blocks_after_threshold(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    statuses = [
        client.post("/v1/auth/login", json={"email": "nadie@example.com", "password": "incorrecta-123"}).status_code
        for _ in range(settings.rate_limit_auth_per_minute + 3)
    ]
    assert 429 in statuses
    assert statuses.index(429) >= settings.rate_limit_auth_per_minute
