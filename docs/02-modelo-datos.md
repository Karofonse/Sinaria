# Modelo de datos

Fuente de verdad: migraciones Alembic en `apps/api/alembic/versions/`. Este documento describe la intención; si difieren, gana la migración y se corrige el documento.

## Convenciones
- Claves primarias `uuid` (generadas en la aplicación con `uuid4`).
- Importes monetarios en **enteros** (centavos COP o créditos enteros). Nunca `float`.
- Todas las tablas tienen `created_at timestamptz NOT NULL DEFAULT now()`; las mutables tienen `updated_at`.
- Borrado lógico solo donde se indica (`deleted_at`); las tablas financieras y de auditoría son inmutables.

## Tablas

| Tabla | Propósito | Restricciones clave |
|---|---|---|
| `users` | Cuenta | `email` único (case-insensitive), `status` ∈ {active, suspended}, `email_verified_at` |
| `roles` | Catálogo de roles | `name` único (`user`, `admin`, `support`) |
| `user_roles` | Asignación | PK `(user_id, role_id)` |
| `plans` | Planes (fase futura) | `code` único |
| `credit_packages` | Paquetes comprables | `code` único, `credits > 0`, `price_cop_cents > 0`, `active` |
| `wallets` | Saldo por usuario | `user_id` único; `available_credits >= 0`; `reserved_credits >= 0`; `version` para diagnóstico |
| `credit_transactions` | **Libro mayor inmutable** | `idempotency_key` único; `available_delta`, `reserved_delta` enteros; `kind` ∈ {purchase, reserve, consume, release, refund, chargeback, grant, adjustment}; trigger que bloquea UPDATE/DELETE |
| `payments` | Pago con el proveedor | `reference` único; `provider_transaction_id` único (nullable); `status` ∈ {pending, approved, declined, voided, error, refunded, chargeback} |
| `payment_events` | Eventos del webhook | `dedupe_key` único; `signature_valid` boolean; cuerpo y firma protegidos por trigger (solo `processed_at` puede cambiar) |
| `provider_models` | Catálogo y precios por modelo | `(provider, model_key)` único; `enabled`; `min_duration_s`, `max_duration_s`; `credits_per_generation`; `supports_seed` |
| `generation_jobs` | Trabajo de generación | `(user_id, idempotency_key)` único; `status` ∈ {pending, processing, completed, failed}; `reserved_credits > 0`; CHECK de transiciones válidas en código |
| `generated_tracks` | Pista producida | `generation_job_id` único; `owner_id` = usuario del job; `storage_key` único; `deleted_at` |
| `provider_usage` | Coste por operación | `(provider, provider_job_ref)` índice; `estimated_cost_micros`, `actual_cost_micros` |
| `subscriptions` | Suscripción (fase futura) | `provider_subscription_id` único; `status` |
| `admin_audit_logs` | Auditoría administrativa | Inmutable (trigger); `actor_user_id`, `action`, `target_type`, `target_id`, `before`, `after`, `reason` |

## Relaciones
- `users 1—1 wallets`
- `users 1—N credit_transactions` (vía wallet)
- `users 1—N generation_jobs 1—0..1 generated_tracks`
- `generation_jobs N—1 provider_models`
- `payments N—1 users`, `payments N—1 credit_packages`, `payment_events N—0..1 payments`
- `provider_usage N—0..1 generation_jobs`

## Invariante financiera

Para cada wallet:
```
wallets.available_credits = Σ credit_transactions.available_delta (where wallet_id)
wallets.reserved_credits  = Σ credit_transactions.reserved_delta  (where wallet_id)
```
El reconciliador verifica esta igualdad. Cada operación del libro mayor mueve valores entre `available` y `reserved` o los crea/destruye con un motivo explícito:

| kind | available_delta | reserved_delta | Motivo |
|---|---|---|---|
| purchase / grant | +n | 0 | Pago confirmado / concesión |
| reserve | −c | +c | Inicio de generación |
| consume | 0 | −c | Generación completada |
| release | +c | −c | Generación fallida |
| refund | +n | 0 | Reembolso del proveedor de pago compensado |
| chargeback | −n (puede dejar available en 0; si no hay saldo, queda deuda registrada como ajuste pendiente) | 0 | Contracargo |
| adjustment | ±n | 0 | Ajuste administrativo (con motivo y actor) |

Nota sobre contracargos: si el saldo disponible es menor que el contracargo, la operación no puede dejar el saldo en negativo. El sistema reserva la diferencia como **deuda pendiente** en `payments` (estado `chargeback`) y bloquea nuevas reservas hasta su regularización; esta regla requiere decisión de negocio (ver plan §riesgos).

## Índices previstos
- `generation_jobs (status, updated_at)` para el reconciliador.
- `generation_jobs (user_id, created_at DESC)` para el historial.
- `generated_tracks (owner_id, created_at DESC) WHERE deleted_at IS NULL`.
- `generated_tracks` búsqueda por título: `pg_trgm` GIN (fase 7).
- `credit_transactions (wallet_id, created_at)`.
- `provider_usage (created_at)` para presupuestos diarios.

## Retención y eliminación
| Dato | Retención | Acción al vencer |
|---|---|---|
| Pistas borradas por el usuario | 30 días | Purga física del archivo y de la fila |
| Archivos de pistas activas | Mientras la cuenta exista | Purga al borrar la cuenta (con 30 días de gracia) |
| `credit_transactions`, `payments`, `payment_events` | Según obligación fiscal/contable (decisión legal pendiente, mínimo 5 años como referencia) | Conservar; anonimizar datos personales no necesarios |
| `admin_audit_logs` | 2 años | Archivo |
| Logs de aplicación | 30 días | Rotación del proveedor |
| Tokens de verificación/recuperación | Hasta caducidad (≤ 24 h) | Purga diaria |
