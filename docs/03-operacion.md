# Operación: configuración de APIs, base de datos, migraciones, pagos, despliegue y CI/CD

> Estado: **guía de referencia**. Las secciones marcadas **[PENDIENTE]** describen pasos que no se han ejecutado porque requieren cuentas, credenciales o autorización del propietario.

## 1. Configuración de APIs externas

Todas las claves se leen de variables de entorno (ver `.env.example`). Ninguna clave debe llegar al navegador: el frontend solo habla con la API propia.

| Servicio | Variables | Estado |
|---|---|---|
| fal.ai (Stable Audio 3 Small) | `FAL_ENABLED`, `FAL_API_KEY` | **[PENDIENTE]** Desactivado. Antes de activar: verificar endpoint, parámetros, duración máxima, SDK y política de webhooks en la documentación oficial; probar con el mock. Ver `00-analisis-fase0.md` §2.1 |
| Stability AI (Stable Audio 3.0) | `STABILITY_ENABLED`, `STABILITY_API_KEY` | **[PENDIENTE]** Bloqueado por tarifa oficial y licencia comercial |
| Wompi Colombia | `PAYMENTS_ENABLED`, claves y secretos de eventos (por definir) | **[PENDIENTE]** Ver §4 |
| Supabase (PostgreSQL + Auth) | `DATABASE_URL` | **[PENDIENTE]** La BD funciona con cualquier PostgreSQL 16. La migración de identidad a Supabase Auth requiere decisión (ver `01-arquitectura.md` §5) |
| Cloudflare R2 | `STORAGE_BACKEND=s3`, endpoint, bucket, claves | **[PENDIENTE]** `app/storage/s3.py` es un esqueleto que lanza `NotImplementedError` |

Reglas:
- Un proveedor se activa con su interruptor **y** con la clave. Sin interruptor, el adaptador rechaza cualquier llamada con `provider_disabled`.
- Activar un proveedor de pago o de generación con coste real requiere autorización expresa del propietario y un presupuesto configurado (`DAILY_GLOBAL_CREDIT_BUDGET`, `USER_DAILY_CREDIT_LIMIT`).

## 2. Base de datos

- Motor: PostgreSQL 16 (probado localmente con 16.15).
- Esquema: una sola migración inicial `apps/api/alembic/versions/0001_initial_schema.py`. Es la **fuente de verdad**; los modelos ORM (`app/models.py`) la reflejan.
- Integridad que vive en la BD y no solo en Python:
  - `wallets`: `CHECK (available_credits >= 0 AND reserved_credits >= 0)`.
  - `credit_transactions`: `UNIQUE (idempotency_key)`, `CHECK` por tipo de movimiento (un `reserve` debe mover exactamente lo mismo de disponible a reservado, etc.), trigger que rechaza `UPDATE` y `DELETE`.
  - `payment_events`: trigger que rechaza borrado y cambios en cuerpo, firma y claves; solo `processed_at` puede actualizarse.
  - `admin_audit_logs`: inmutable por trigger.
  - `generation_jobs`: `UNIQUE (user_id, idempotency_key)`, `CHECK` de estados y de coherencia de `completed_at`.
  - `generated_tracks.generation_job_id`: `UNIQUE`; cada pista pertenece a un usuario y a un trabajo.

## 3. Migraciones

```bash
cd apps/api
export DATABASE_URL=postgresql+psycopg://USUARIO:CLAVE@HOST:5432/BASE
alembic upgrade head          # aplicar
alembic current               # ver versión
alembic downgrade -1          # revertir la última (solo en dev)
python -m app.seed            # roles, modelos y paquetes de referencia (idempotente)
```

Reglas:
- Ninguna migración modifica filas de `credit_transactions`, `payment_events` o `admin_audit_logs`. Las correcciones son movimientos nuevos.
- Toda migración nueva se prueba en CI con `upgrade → downgrade base → upgrade`.
- En producción, aplicar migraciones **antes** de desplegar la nueva API, con copia de seguridad previa.
- Los datos de ejemplo de `app/seed.py` (precios) son orientativos: los paquetes se crean **inactivos**.

Reset local (solo desarrollo):
```bash
psql "$ADMIN_URL" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
alembic upgrade head && python -m app.seed
```

## 4. Guía Wompi sandbox **[PENDIENTE]**

No ejecutado. Pasos previstos, a confirmar con la documentación oficial de Wompi Colombia:
1. Crear cuenta sandbox y obtener las claves de prueba. **No** guardarlas en el repositorio.
2. Registrar la URL de eventos del entorno sandbox (cada entorno tiene la suya, según la documentación consultada en búsqueda; verificar).
3. Implementar `POST /v1/webhooks/wompi` leyendo el **cuerpo crudo**, verificando el checksum (`X-Event-Checksum` / `signature.checksum`) con la fórmula oficial (orden de `signature.properties`, `timestamp`, secreto de eventos, SHA-256) y comparando en tiempo constante. Rechazar sin procesar si no coincide.
4. Idempotencia: `payment_events` con `dedupe_key` único; `payments` con transición condicional. Un evento `APPROVED` acredita con clave `purchase:{payment_id}`.
5. Pruebas: eventos sintéticos firmados con el secreto de prueba; duplicados; eventos fuera de orden; `DECLINED`, `VOIDED`, `ERROR`; reembolso y contracargo.
6. Solo después de autorización: habilitar `PAYMENTS_ENABLED=true` en sandbox.

Nota: la guía de la búsqueda mencionaba un checksum distinto para la versión de El Salvador. No aplicarlo a Colombia.

## 5. Despliegue (propuesta, no ejecutada)

| Componente | Opción propuesta | Notas |
|---|---|---|
| Frontend | Vercel | Build con `output: standalone` disponible; `API_INTERNAL_URL` debe apuntar al backend público. Rewrites `/v1/*` al backend |
| API | Plataforma con procesos persistentes (Render, Railway, Fly.io) | Comando: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`. Sin escalado horizontal del worker hasta revisar reconciliación |
| Worker | Proceso separado en la misma plataforma | Comando: `python -m app.worker`. Mismo `DATABASE_URL` y `REDIS_URL` |
| PostgreSQL | Supabase (sandbox y prod, proyectos separados) | Backups diarios y PITR (plan de pago) |
| Redis | Servicio gestionado con persistencia AOF o aceptar pérdida de cola (la reconciliación reencola) | Rate limiting y cola |
| Almacenamiento | Cloudflare R2, bucket privado | **[PENDIENTE]** implementar `s3.py` |

Variables mínimas en sandbox/prod: `APP_ENV`, `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET` (≥32 caracteres), `DOWNLOAD_URL_SECRET` (≥32), `COOKIE_SECURE=true`, `CORS_ORIGINS` (dominio exacto del frontend). La API **no arranca** en `APP_ENV=production` si faltan (validación en `app/core/config.py`).

## 6. Backups y retención

| Dato | Copia | Retención | Restauración |
|---|---|---|---|
| PostgreSQL | Diaria + PITR | 30 días (sandbox 7) | Probar restauración en un proyecto temporal cada trimestre |
| Archivos de audio (R2) | Versionado del bucket o replicación a otro bucket | Igual que la cuenta + 30 días tras borrado | Probar lectura de una muestra mensual |
| Redis | No es fuente de verdad | — | La reconciliación reencola trabajos desde PostgreSQL |
| Secretos | Gestor del proveedor de hosting | Rotación anual o ante incidente | — |

Políticas de borrado de datos: ver `02-modelo-datos.md` (retención y eliminación). Los plazos fiscales de los registros de pago están **pendientes de confirmación legal**.

## 7. CI/CD

- `.github/workflows/ci.yml`: en cada PR y push a `main`:
  - API: `ruff`, migraciones (`upgrade → downgrade → upgrade`) y `pytest` contra PostgreSQL 16 y Redis 7 de servicio.
  - Web: `tsc --noEmit`, `vitest`, `next build`.
- No hay job de despliegue todavía: requiere decidir plataforma y secretos. **[PENDIENTE]**
- Las imágenes Docker se definen en `apps/api/Dockerfile` y `apps/web/Dockerfile`. **No se han construido** en esta sesión (sin daemon Docker).

## 8. Ejecución local sin Docker (lo que se ejecutó aquí)

```bash
# PostgreSQL 16 y Redis 7 locales en 127.0.0.1:5432 y :6379
cd apps/api && python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://sonaria:sonaria_dev@127.0.0.1:5432/sonaria_dev
alembic upgrade head && python -m app.seed
uvicorn app.main:app --port 8000          # API
python -m app.worker                      # worker (otra terminal)
pytest                                    # pruebas (usa sonaria_test)

cd apps/web && npm ci
API_INTERNAL_URL=http://127.0.0.1:8000 npm run build && API_INTERNAL_URL=http://127.0.0.1:8000 npm start   # puerto 3000
npm test
```
