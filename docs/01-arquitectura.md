# Fase 1 — Arquitectura, estructura y flujos

## 1. Visión general

```
Navegador (Next.js, Vercel)
   │  HTTPS, cookie httpOnly  /  Authorization: Bearer
   ▼
API (FastAPI, proceso persistente)  ──────────────►  PostgreSQL (Supabase en prod)
   │   · auth, créditos, generaciones, biblioteca,      (libro mayor, jobs, pistas)
   │     pagos (webhook), admin
   │                                               
   ├──► Redis (cola de trabajos, rate limiting, locks)
   │         ▲
   │         │ BLPOP
   │   Worker (mismo código, otro proceso)
   │         │
   │         ├──► Proveedor musical (adapter: mock | fal | stability)
   │         └──► Almacenamiento privado (local | R2/S3) — descarga inmediata
   │
   └──► Wompi (webhook entrante; llamadas salientes solo tras autorización)
```

Principios:
1. **El servidor es la fuente de verdad** para saldos, precios, propiedad de recursos y roles.
2. **Nada se acredita por el navegador.** Solo el webhook verificado de Wompi o un ajuste administrativo auditado mueven créditos comprados/otorgados.
3. **Toda escritura financiera es idempotente** y ocurre en una transacción con filas bloqueadas.
4. **Los proveedores son reemplazables** mediante adaptadores; el dominio no conoce sus detalles.
5. **Los archivos son privados**; el acceso es por URL firmada de corta duración verificada por el backend.

## 2. Entornos

| Entorno | Propósito | Base de datos | Proveedor musical | Pagos | Almacenamiento |
|---|---|---|---|---|---|
| **dev** | Desarrollo local | PostgreSQL 16 en Docker Compose | `mock` | Sin integrar | Disco local (`./.data/storage`) |
| **sandbox** | Pruebas integradas, QA, demos internas | Supabase proyecto `sonaria-sandbox` | `mock` por defecto; `fal` solo con flag y presupuesto de prueba | Wompi **sandbox** | R2 bucket `sonaria-sandbox-private` |
| **prod** | Usuarios reales | Supabase proyecto `sonaria-prod`, backups diarios + PITR | `fal` / `stability` según aprobación | Wompi producción | R2 bucket `sonaria-prod-private` |

Reglas:
- Ningún entorno comparte secretos ni bases de datos con otro.
- `APP_ENV` ∈ {`development`, `sandbox`, `production`}. En `production` la aplicación **se niega a arrancar** si `DEBUG`, `CORS_ORIGINS=*`, `JWT_SECRET` por defecto o `PAYMENTS_ENABLED=true` sin `WOMPI_*` completos están presentes.
- Los proveedores reales (`fal`, `stability`) tienen un interruptor `PROVIDER_<NOMBRE>_ENABLED` que por defecto es `false`.

## 3. Estructura del monorepo

```
sonaria/
├── apps/
│   ├── api/                      # FastAPI + SQLAlchemy + Alembic + worker
│   │   ├── app/
│   │   │   ├── main.py           # fábrica de la app, middlewares, routers
│   │   │   ├── core/             # config, seguridad, logging, errores, rate limit
│   │   │   ├── db/               # engine, sesión, modelos ORM (Base)
│   │   │   ├── models/           # modelos SQLAlchemy por dominio
│   │   │   ├── schemas/          # Pydantic I/O
│   │   │   ├── domain/
│   │   │   │   ├── credits.py    # libro mayor: reservar, consumir, liberar, acreditar
│   │   │   │   ├── generations.py# máquina de estados de jobs
│   │   │   │   └── budget.py     # presupuestos por usuario y global
│   │   │   ├── providers/        # interfaz MusicProvider + mock, fal, stability
│   │   │   ├── storage/          # interfaz ObjectStorage + local, s3
│   │   │   ├── payments/         # Wompi: verificación de webhook, reconciliación
│   │   │   ├── routers/          # auth, me, wallet, generations, tracks, billing, admin, health
│   │   │   └── worker.py         # consumidor Redis + reconciliador
│   │   ├── alembic/              # migraciones versionadas
│   │   ├── tests/                # unit, integration, concurrencia, idempotencia
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── web/                      # Next.js App Router + Tailwind + TypeScript
│       ├── app/
│       │   ├── [locale]/         # es | en
│       │   │   ├── page.tsx                 # inicio
│       │   │   ├── (auth)/register|login/
│       │   │   ├── (app)/studio|library|library/[id]|billing|dashboard|profile/
│       │   │   ├── admin/
│       │   │   ├── terms|privacy/
│       │   │   └── not-found.tsx, error.tsx
│       ├── components/ lib/ (api client, i18n) messages/ (es.json, en.json)
│       ├── middleware.ts         # redirección de locale y protección de rutas (UX; la seguridad real está en la API)
│       └── Dockerfile
├── infra/
│   ├── docker/                   # compose de desarrollo
│   └── ci/                       # notas de workflows
├── docs/                         # este directorio
├── .github/workflows/            # CI (lint, tests, build)
├── docker-compose.yml
├── .env.example
└── README.md
```

## 4. Modelo de datos (resumen; detalle en `02-modelo-datos.md`)

Tablas: `users`, `roles`, `user_roles`, `plans`, `credit_packages`, `wallets`, `credit_transactions`, `payments`, `payment_events`, `generation_jobs`, `generated_tracks`, `provider_models`, `provider_usage`, `subscriptions`, `admin_audit_logs`.

Invariantes implementadas en PostgreSQL (no solo en Python):
- `wallets.available_credits >= 0` y `wallets.reserved_credits >= 0` (CHECK).
- `credit_transactions` es inmutable: triggers `BEFORE UPDATE OR DELETE` lanzan excepción.
- `credit_transactions.idempotency_key` es único: un mismo movimiento no puede registrarse dos veces.
- `payment_events` y `payments.provider_transaction_id` son únicos.
- `generation_jobs (user_id, idempotency_key)` es único.
- `generated_tracks.generation_job_id` es único y `NOT NULL` con FK a `generation_jobs` y `users`.
- `admin_audit_logs` es inmutable.

## 5. Decisión de autenticación

Supabase Auth es el destino declarado, pero no hay credenciales ni acceso verificable en esta sesión. Para no bloquear el desarrollo se implementa:
- Contraseñas con `scrypt` (stdlib de Python), parámetros explícitos.
- Sesión: JWT firmado HS256 de vida corta (15 min) + refresh token opaco rotatorio almacenado hasheado. *(En la fase actual se entrega access token; la rotación de refresh queda pendiente.)*
- Verificación de correo y recuperación de contraseña: diseñadas como tokens de un solo uso con hash en BD; el envío de correo queda detrás de una interfaz `Mailer` (consola en dev).

**Alternativa recomendada para producción**: migrar la identidad a Supabase Auth y mantener `users` como perfil enlazado por `auth_user_id`. Requiere aprobación humana (ver `04-plan-y-riesgos.md`).

## 6. Flujos principales

### 6.1 Compra de créditos (pendiente de autorización)
1. Usuario elige paquete → `POST /billing/checkout` crea `payments` con estado `pending` y referencia única. **Bloqueado** por `PAYMENTS_ENABLED=false`.
2. Wompi procesa el pago y notifica por webhook `POST /webhooks/wompi`.
3. El endpoint: lee el cuerpo crudo; verifica checksum; registra `payment_events` (idempotente por clave); si el evento es `APPROVED` y el pago está `pending`, en una transacción: marca `approved` y ejecuta `credits.purchase(payment_id)` con clave `purchase:{payment_id}`.
4. `DECLINED`/`ERROR`/`VOIDED` actualizan estado sin acreditar. Un reembolso o contracargo aprobado genera `refund`/`chargeback` con débito compensatorio, nunca borrado.
5. Un reconciliador consulta pagos `pending` antiguos (cuando la API de consulta esté verificada).

### 6.2 Generación musical
1. `POST /generations` con cabecera `Idempotency-Key` (obligatoria). Validación Pydantic: prompt, negativo, género, ánimo, instrumentos, duración dentro del modelo, semilla si soportada, modelo habilitado.
2. Transacción única:
   - Si ya existe job `(user, idempotency_key)`, devolverlo (sin cobrar de nuevo).
   - Verificar presupuesto (usuario y global diario).
   - `SELECT … FROM wallets WHERE user_id = … FOR UPDATE`; si `available < coste` → 402.
   - Mover `coste` de `available` a `reserved`; insertar movimiento `reserve` con clave `reserve:{job_id}`; insertar job `pending`.
3. Commit y encolado en Redis (`LPUSH sonaria:jobs`). Si el encolado falla, el job queda `pending` y el reconciliador lo reencola; no se pierde el reserva.
4. Worker: `UPDATE generation_jobs SET status='processing', attempts=attempts+1 WHERE id=? AND status='pending'`. Si no afecta filas, se descarta (duplicado).
5. Worker llama al adaptador: `submit` → guarda `provider_job_id` → `poll` con backoff → `result`.
6. Worker descarga el archivo, lo guarda en storage privado, crea `generated_tracks` y en la misma transacción transición a `completed` y movimiento `consume` (`reserved -= coste`, clave `consume:{job_id}`). Se registra `provider_usage`.
7. Errores:
   - Transitorio (timeout, 429, 5xx): reintenta con backoff hasta `MAX_ATTEMPTS`.
   - Permanente (prompt rechazado, modelo deshabilitado, duración inválida): `failed` + `release` (`reserved -= coste`, `available += coste`).
   - Proveedor completó pero la descarga falló: reintento de descarga usando `provider_job_id`; si agota reintentos, `failed` + `release`. Se registra en `provider_usage` como coste incurrido para revisión.
8. Cliente desconectado: el estado vive en BD; al volver, `GET /generations/{id}` devuelve el resultado.

### 6.3 Reconciliación
Job programado (cada 5 min en sandbox/prod):
- Jobs `processing` sin actualización > `STUCK_AFTER_S` → reencolar si `attempts < MAX`, si no fallar + liberar.
- Jobs `pending` sin encolar → reencolar.
- Verificar invariantes: `wallets.reserved_credits = Σ reserved_delta` del libro mayor; `available` idem. Diferencias → alerta y registro en `admin_audit_logs` (no corrección automática).

### 6.4 Biblioteca y descarga
- `GET /tracks` paginado con búsqueda (`q`) y filtros (modelo, rango de fechas). Siempre filtrado por `owner_id = current_user`.
- `PATCH /tracks/{id}` renombrado; `DELETE /tracks/{id}` = borrado lógico (`deleted_at`); purga física tras periodo de retención.
- `GET /tracks/{id}/download-url` → URL firmada con HMAC y caducidad de 5 min; el endpoint de descarga valida firma, caducidad y propietario.

### 6.5 Administración
- Todas las rutas `/admin/*` pasan por dependencia `require_role("admin")` en el servidor.
- Cada acción sensible escribe en `admin_audit_logs` en la misma transacción.
- Ajuste de créditos: `POST /admin/users/{id}/credit-adjustments` con motivo obligatorio y clave de idempotencia.

## 7. Seguridad (diseño)

- CORS: lista explícita de orígenes desde `CORS_ORIGINS`.
- Rate limiting por IP y por usuario en Redis (ventana fija) en login, registro, generación y webhook.
- Cabeceras: `X-Content-Type-Options`, `Referrer-Policy`, `Strict-Transport-Security` en prod, CSP en el frontend.
- Validación: Pydantic en API; límites de tamaño de cuerpo en prompts (2 000 caracteres) y webhooks.
- Errores: formato uniforme sin trazas en prod; `request_id` en cada respuesta y log.
- Logs JSON estructurados (`request_id`, `user_id`, `job_id`, `provider`); nunca secretos ni contraseñas.
- Secretos solo por variables de entorno/gestor del proveedor de hosting; `.env` ignorado por git.

## 8. Observabilidad

- Logs JSON por stdout.
- Métricas Prometheus en `/metrics` (protegido por token en prod): latencia por ruta, jobs por estado, errores por clase de proveedor, saldo reservado total.
- Alertas recomendadas: tasa de fallos > 10 % en 15 min; jobs estancados > 0 durante 10 min; diferencia de reconciliación ≠ 0; webhooks con checksum inválido > umbral.
- *Implementación de métricas: incluida en el plan de Fase 8.*

## 9. Plan de implementación

Ver `04-plan-y-riesgos.md` §2. Esta sesión ejecuta: Fase 0, Fase 1, base de Fase 2 (auth + dashboard), Fase 3 (generación con mock), Fase 5 (libro mayor y pruebas de concurrencia). Fase 4, 6 y 7 quedan preparadas con interfaces, sin llamadas reales.
