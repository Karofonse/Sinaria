import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import get_settings


def _strip(v: str | None) -> str | None:
    if v is None:
        return None
    v = " ".join(v.split())
    return v or None


class RegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=2, max_length=60)
    locale: Literal["es", "en"] = "es"

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()

    @field_validator("display_name")
    @classmethod
    def _clean(cls, v: str) -> str:
        return " ".join(v.split())


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    display_name: str
    locale: str
    status: str
    roles: list[str]
    created_at: datetime


class BalanceOut(BaseModel):
    available_credits: int
    reserved_credits: int


class LedgerEntryOut(BaseModel):
    id: uuid.UUID
    kind: str
    available_delta: int
    reserved_delta: int
    reference_type: str | None
    reference_id: str | None
    created_at: datetime


class GenerationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_key: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=3, max_length=get_settings().max_prompt_chars)
    negative_prompt: str | None = Field(default=None, max_length=500)
    genre: str | None = Field(default=None, max_length=64)
    mood: str | None = Field(default=None, max_length=64)
    instruments: list[str] = Field(default_factory=list, max_length=10)
    duration_seconds: int = Field(ge=1, le=600)
    seed: int | None = Field(default=None, ge=0, le=2**32 - 1)
    instrumental: Literal[True] = True

    @field_validator("prompt", "negative_prompt", "genre", "mood")
    @classmethod
    def _normalize(cls, v: str | None) -> str | None:
        return _strip(v)

    @field_validator("instruments")
    @classmethod
    def _instruments(cls, v: list[str]) -> list[str]:
        cleaned = []
        for item in v:
            s = _strip(item)
            if s and len(s) <= 64 and s not in cleaned:
                cleaned.append(s)
        return cleaned


class GenerationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: str
    prompt: str
    negative_prompt: str | None
    genre: str | None
    mood: str | None
    instruments: list[str]
    duration_seconds: int
    seed: int | None
    reserved_credits: int
    model_key: str
    provider: str
    error_code: str | None
    error_message: str | None
    track_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class TrackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    generation_job_id: uuid.UUID
    mime_type: str
    size_bytes: int
    duration_seconds: float
    provider: str
    model_key: str
    created_at: datetime


class TrackUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def _clean(cls, v: str) -> str:
        cleaned = " ".join(v.split())
        if not cleaned:
            raise ValueError("El título no puede estar vacío")
        return cleaned


class DownloadUrlOut(BaseModel):
    url: str
    expires_at: int


class ProviderModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    model_key: str
    display_name: str
    provider: str
    min_duration_s: int
    max_duration_s: int
    credits_per_generation: int
    supports_seed: bool
    supports_negative_prompt: bool
    output_format: str


class PackageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str
    credits: int
    price_cop_cents: int


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    display_name: str
    status: str
    created_at: datetime


class SuspendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=500)


class CreditAdjustIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delta: int = Field(ge=-100_000, le=100_000)
    reason: str = Field(min_length=5, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=120)


class ProviderModelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    credits_per_generation: int | None = Field(default=None, ge=1, le=10_000)
    reason: str = Field(min_length=5, max_length=500)
