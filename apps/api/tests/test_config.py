import pytest

from app.core.config import Settings


def test_production_rejects_insecure_defaults():
    with pytest.raises(ValueError) as exc:
        Settings(app_env="production")
    msg = str(exc.value)
    assert "JWT_SECRET" in msg and "COOKIE_SECURE" in msg and "DEBUG" not in msg


def test_production_accepts_hardened_config():
    s = Settings(
        app_env="production",
        jwt_secret="x" * 40,
        download_url_secret="y" * 40,
        cookie_secure=True,
        cors_origins="https://app.sonaria.example",
    )
    assert s.cors_origin_list == ["https://app.sonaria.example"]


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValueError):
        Settings(
            app_env="production",
            jwt_secret="x" * 40,
            download_url_secret="y" * 40,
            cookie_secure=True,
            cors_origins="*",
        )
