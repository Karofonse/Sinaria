"""Esquema inicial: usuarios, roles, billetera y libro mayor inmutable, pagos, generaciones,
pistas, uso de proveedores, suscripciones (preparado) y auditoría administrativa.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DDL = """
-- ---------------------------------------------------------------- identidad y roles
CREATE TABLE roles (
    id          integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name        varchar(40) NOT NULL UNIQUE,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id                 uuid PRIMARY KEY,
    email              varchar(320) NOT NULL UNIQUE,
    password_hash      varchar(255) NOT NULL,
    display_name       varchar(120) NOT NULL,
    locale             varchar(5) NOT NULL DEFAULT 'es',
    status             varchar(20) NOT NULL DEFAULT 'active',
    email_verified_at  timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_users_email_lower CHECK (email = lower(email)),
    CONSTRAINT ck_users_status CHECK (status IN ('active', 'suspended')),
    CONSTRAINT ck_users_locale CHECK (locale IN ('es', 'en'))
);

CREATE TABLE user_roles (
    user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id     integer NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, role_id)
);

-- ---------------------------------------------------------------- catálogo comercial
CREATE TABLE plans (
    id               uuid PRIMARY KEY,
    code             varchar(40) NOT NULL UNIQUE,
    name             varchar(120) NOT NULL,
    monthly_credits  integer NOT NULL CHECK (monthly_credits >= 0),
    price_cop_cents  bigint NOT NULL CHECK (price_cop_cents >= 0),
    active           boolean NOT NULL DEFAULT true,
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE credit_packages (
    id               uuid PRIMARY KEY,
    code             varchar(40) NOT NULL UNIQUE,
    name             varchar(120) NOT NULL,
    credits          integer NOT NULL CHECK (credits > 0),
    price_cop_cents  bigint NOT NULL CHECK (price_cop_cents > 0),
    active           boolean NOT NULL DEFAULT true,
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- libro mayor
CREATE TABLE wallets (
    id                 uuid PRIMARY KEY,
    user_id            uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE RESTRICT,
    available_credits  bigint NOT NULL DEFAULT 0,
    reserved_credits   bigint NOT NULL DEFAULT 0,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_wallets_available_nonneg CHECK (available_credits >= 0),
    CONSTRAINT ck_wallets_reserved_nonneg CHECK (reserved_credits >= 0)
);

CREATE TABLE credit_transactions (
    id               uuid PRIMARY KEY,
    wallet_id        uuid NOT NULL REFERENCES wallets(id) ON DELETE RESTRICT,
    kind             varchar(20) NOT NULL,
    available_delta bigint NOT NULL,
    reserved_delta  bigint NOT NULL,
    idempotency_key  varchar(160) NOT NULL UNIQUE,
    reference_type   varchar(40),
    reference_id    varchar(64),
    actor_user_id    uuid REFERENCES users(id) ON DELETE RESTRICT,
    reason           text,
    metadata         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_ct_kind CHECK (kind IN
        ('purchase', 'grant', 'refund', 'chargeback', 'reserve', 'consume', 'release', 'adjustment')),
    -- Cada tipo de movimiento tiene una forma fija de deltas: la BD rechaza movimientos mal formados.
    CONSTRAINT ck_ct_shape CHECK (
        (kind = 'reserve'    AND available_delta < 0 AND reserved_delta = -available_delta)
        OR (kind = 'consume' AND available_delta = 0 AND reserved_delta < 0)
        OR (kind = 'release' AND reserved_delta < 0 AND available_delta = -reserved_delta)
        OR (kind IN ('purchase', 'grant', 'refund') AND reserved_delta = 0 AND available_delta > 0)
        OR (kind = 'chargeback' AND reserved_delta = 0 AND available_delta < 0)
        OR (kind = 'adjustment' AND reserved_delta = 0 AND available_delta <> 0)
    ),
    CONSTRAINT ck_ct_adjustment_reason CHECK (kind <> 'adjustment' OR reason IS NOT NULL)
);
CREATE INDEX ix_ct_wallet_created ON credit_transactions (wallet_id, created_at);

-- ---------------------------------------------------------------- pagos
CREATE TABLE payments (
    id                       uuid PRIMARY KEY,
    user_id                  uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    package_id               uuid NOT NULL REFERENCES credit_packages(id) ON DELETE RESTRICT,
    provider                 varchar(20) NOT NULL DEFAULT 'wompi',
    reference                varchar(80) NOT NULL UNIQUE,
    provider_transaction_id  varchar(120) UNIQUE,
    amount_cop_cents         bigint NOT NULL CHECK (amount_cop_cents > 0),
    status                   varchar(20) NOT NULL DEFAULT 'pending',
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_payments_status CHECK (status IN
        ('pending', 'approved', 'declined', 'voided', 'error', 'refunded', 'chargeback'))
);

-- Eventos recibidos del proveedor. El cuerpo y la firma no se modifican; processed_at sí.
CREATE TABLE payment_events (
    id               uuid PRIMARY KEY,
    provider         varchar(20) NOT NULL,
    dedupe_key       varchar(200) NOT NULL UNIQUE,
    event_type       varchar(80) NOT NULL,
    payment_id       uuid REFERENCES payments(id) ON DELETE RESTRICT,
    signature_valid  boolean NOT NULL,
    raw_body         text NOT NULL,
    processed_at     timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- generación
CREATE TABLE provider_models (
    id                       uuid PRIMARY KEY,
    provider                 varchar(40) NOT NULL,
    model_key                varchar(100) NOT NULL,
    display_name             varchar(120) NOT NULL,
    enabled                  boolean NOT NULL DEFAULT false,
    min_duration_s           integer NOT NULL CHECK (min_duration_s >= 1),
    max_duration_s           integer NOT NULL,
    credits_per_generation   integer NOT NULL CHECK (credits_per_generation > 0),
    supports_seed            boolean NOT NULL DEFAULT false,
    supports_negative_prompt boolean NOT NULL DEFAULT false,
    output_format            varchar(10) NOT NULL DEFAULT 'wav',
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_provider_models_provider_key UNIQUE (provider, model_key),
    CONSTRAINT ck_pm_duration CHECK (max_duration_s >= min_duration_s)
);

CREATE TABLE generation_jobs (
    id                  uuid PRIMARY KEY,
    user_id             uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    provider_model_id   uuid NOT NULL REFERENCES provider_models(id) ON DELETE RESTRICT,
    idempotency_key     varchar(128) NOT NULL,
    request_fingerprint varchar(64) NOT NULL,
    status              varchar(20) NOT NULL DEFAULT 'pending',
    prompt              text NOT NULL,
    negative_prompt     text,
    genre               varchar(64),
    mood                varchar(64),
    instruments         jsonb NOT NULL DEFAULT '[]'::jsonb,
    duration_seconds    integer NOT NULL CHECK (duration_seconds >= 1),
    seed                bigint,
    reserved_credits    integer NOT NULL CHECK (reserved_credits > 0),
    provider_job_ref    varchar(160),
    attempts            integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    error_code          varchar(64),
    error_message       text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    completed_at        timestamptz,
    CONSTRAINT uq_generation_jobs_user_idem UNIQUE (user_id, idempotency_key),
    CONSTRAINT ck_gj_status CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    CONSTRAINT ck_gj_completed_at CHECK ((status IN ('completed', 'failed')) = (completed_at IS NOT NULL))
);
CREATE INDEX ix_gj_status_updated ON generation_jobs (status, updated_at);
CREATE INDEX ix_gj_user_created ON generation_jobs (user_id, created_at DESC);
CREATE INDEX ix_gj_created ON generation_jobs (created_at);

CREATE TABLE generated_tracks (
    id                  uuid PRIMARY KEY,
    owner_id            uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    generation_job_id   uuid NOT NULL UNIQUE REFERENCES generation_jobs(id) ON DELETE RESTRICT,
    title               varchar(200) NOT NULL,
    storage_key         varchar(512) NOT NULL UNIQUE,
    mime_type           varchar(80) NOT NULL,
    size_bytes          bigint NOT NULL CHECK (size_bytes > 0),
    duration_seconds    double precision NOT NULL CHECK (duration_seconds > 0),
    sha256              varchar(64) NOT NULL,
    provider            varchar(40) NOT NULL,
    model_key           varchar(100) NOT NULL,
    deleted_at          timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_tracks_owner_created ON generated_tracks (owner_id, created_at DESC) WHERE deleted_at IS NULL;

CREATE TABLE provider_usage (
    id                      uuid PRIMARY KEY,
    provider                varchar(40) NOT NULL,
    model_key               varchar(100) NOT NULL,
    user_id                 uuid REFERENCES users(id) ON DELETE RESTRICT,
    generation_job_id       uuid REFERENCES generation_jobs(id) ON DELETE RESTRICT,
    outcome                 varchar(20) NOT NULL,
    credits_charged         integer NOT NULL DEFAULT 0 CHECK (credits_charged >= 0),
    estimated_cost_micros   bigint NOT NULL DEFAULT 0 CHECK (estimated_cost_micros >= 0),
    actual_cost_micros      bigint CHECK (actual_cost_micros IS NULL OR actual_cost_micros >= 0),
    created_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_usage_provider_created ON provider_usage (provider, created_at);

CREATE TABLE subscriptions (
    id                         uuid PRIMARY KEY,
    user_id                    uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    plan_id                    uuid NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
    status                     varchar(20) NOT NULL,
    provider_subscription_id   varchar(120) UNIQUE,
    current_period_start       timestamptz,
    current_period_end         timestamptz,
    created_at                 timestamptz NOT NULL DEFAULT now(),
    updated_at                 timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- auditoría administrativa
CREATE TABLE admin_audit_logs (
    id             uuid PRIMARY KEY,
    actor_user_id  uuid REFERENCES users(id) ON DELETE RESTRICT,
    action         varchar(80) NOT NULL,
    target_type    varchar(40) NOT NULL,
    target_id      varchar(64) NOT NULL,
    before         jsonb,
    after          jsonb,
    reason         text,
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- inmutabilidad
CREATE OR REPLACE FUNCTION sonaria_forbid_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La tabla % es de solo inserción (append-only)', TG_TABLE_NAME
        USING ERRCODE = 'insufficient_privilege';
END;
$$;

CREATE TRIGGER trg_credit_transactions_immutable
    BEFORE UPDATE OR DELETE ON credit_transactions
    FOR EACH ROW EXECUTE FUNCTION sonaria_forbid_mutation();

CREATE TRIGGER trg_admin_audit_logs_immutable
    BEFORE UPDATE OR DELETE ON admin_audit_logs
    FOR EACH ROW EXECUTE FUNCTION sonaria_forbid_mutation();

-- Los eventos de pago conservan cuerpo y firma; solo processed_at puede cambiar.
CREATE OR REPLACE FUNCTION sonaria_payment_event_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'payment_events no admite borrado' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF (NEW.id, NEW.provider, NEW.dedupe_key, NEW.event_type, NEW.payment_id, NEW.signature_valid, NEW.raw_body)
       IS DISTINCT FROM
       (OLD.id, OLD.provider, OLD.dedupe_key, OLD.event_type, OLD.payment_id, OLD.signature_valid, OLD.raw_body) THEN
        RAISE EXCEPTION 'payment_events: solo processed_at puede modificarse' USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_payment_events_guard
    BEFORE UPDATE OR DELETE ON payment_events
    FOR EACH ROW EXECUTE FUNCTION sonaria_payment_event_guard();

-- ---------------------------------------------------------------- datos de referencia
INSERT INTO roles (name) VALUES ('user'), ('admin'), ('support');
"""

_DOWN = """
DROP TABLE IF EXISTS subscriptions, provider_usage, generated_tracks, generation_jobs,
    provider_models, payment_events, payments, credit_transactions, wallets,
    credit_packages, plans, admin_audit_logs, user_roles, roles, users CASCADE;
DROP FUNCTION IF EXISTS sonaria_forbid_mutation();
DROP FUNCTION IF EXISTS sonaria_payment_event_guard();
"""


def upgrade() -> None:
    op.execute(_DDL)


def downgrade() -> None:
    op.execute(_DOWN)
