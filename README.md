# Sonaria

Plataforma SaaS de generación de música instrumental con IA. Monorepo con API (FastAPI + worker) y frontend (Next.js).

> **Estado:** base funcional verificada en local. No está desplegada. Pagos, proveedores reales de generación y almacenamiento R2 **no están activos** y requieren autorización y credenciales del propietario. Ver [Estado](#estado) y `docs/04-plan-y-riesgos.md`.

## Documentación

| Documento | Contenido |
|---|---|
| `docs/00-analisis-fase0.md` | Requisitos, proveedores, licencias, costos, riesgos y verificaciones pendientes |
| `docs/01-arquitectura.md` | Arquitectura, entornos (dev / sandbox / prod), estructura, flujos, seguridad |
| `docs/02-modelo-datos.md` | Modelo de datos, invariantes financieras, retención |
| `docs/03-operacion.md` | Configuración de APIs, base de datos, migraciones, Wompi sandbox, despliegue, backups, CI/CD |
| `docs/04-plan-y-riesgos.md` | Estado por fase, decisiones pendientes y riesgos |
| `docs/05-checklist-produccion.md` | Checklist de seguridad y lanzamiento |

## Estructura

```
apps/api/        FastAPI, SQLAlchemy, Alembic, worker Redis, pruebas (pytest)
apps/web/        Next.js App Router, Tailwind, i18n es/en, pruebas (vitest), E2E (Playwright)
docs/            Documentación de arquitectura, operación y checklist
.github/         CI (lint, migraciones, pruebas, build)
docker-compose.yml  Desarrollo (requiere Docker)
.env.example     Variables de entorno (copiar a .env; nunca commitear .env)
```

## Arranque local

Requisitos: Python 3.12+, Node 22+, PostgreSQL 16, Redis 7. (Con Docker: `docker compose up --build`, sin verificar en esta sesión.)

```bash
# 1. API
cd apps/api
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://USUARIO:CLAVE@127.0.0.1:5432/sonaria
alembic upgrade head
SEED_ADMIN_EMAIL=admin@example.com SEED_ADMIN_PASSWORD=cambia-esta-clave python -m app.seed
uvicorn app.main:app --port 8000        # API en http://127.0.0.1:8000/docs
python -m app.worker                    # worker de generaciones (otra terminal)

# 2. Web
cd apps/web
npm ci
API_INTERNAL_URL=http://127.0.0.1:8000 npm run build
API_INTERNAL_URL=http://127.0.0.1:8000 npm start   # http://localhost:3000
```

Pruebas:
```bash
cd apps/api && pytest                   # usa sonaria_test; se niega si el nombre no termina en _test
cd apps/web && npm test && npm run typecheck
cd apps/web && PLAYWRIGHT_MODULE=<ruta a playwright> npm run e2e   # requiere API, worker, web y admin
```

## Estado

| Área | Estado |
|---|---|
| Registro, login, logout, sesión en cookie httpOnly, roles | Hecho |
| Recuperación de contraseña y verificación de correo | **No implementado** |
| Estudio: prompt, negativo, género, ánimo, instrumentos, duración, semilla | Hecho (modelo mock) |
| "Mejorar prompt" | **No implementado** |
| Generación asíncrona, estados, reintentos, liberación de créditos, reconciliación | Hecho |
| Idempotencia (cabecera `Idempotency-Key`, reintentos de red, doble clic) | Hecho |
| Libro mayor inmutable, saldos ≥ 0 en BD, concurrencia | Hecho |
| Biblioteca: listado, búsqueda por título, renombrar, borrar (lógico), reproductor, descarga firmada | Hecho (almacenamiento local, WAV) |
| Proveedor mock | Hecho (activo por defecto) |
| fal.ai Stable Audio Small | **Esqueleto desactivado**; falta verificar API oficial |
| Stability AI Stable Audio 3.0 | **Esqueleto desactivado**; falta tarifa y licencia |
| Wompi (checkout y webhook) | **No implementado**; endpoint responde 503 |
| Almacenamiento R2/S3 | **No implementado** (`app/storage/s3.py` lanza error) |
| Supabase Auth | **No integrado** (auth propia; decisión pendiente) |
| Panel de administración (usuarios, suspensión, ajustes auditados, métricas, precios) | Hecho (básico) |
| Presupuestos diarios global y por usuario | Hecho |
| Métricas Prometheus y alertas | **No implementado** |
| Docker / Compose | Escritos; **no construidos** (sin daemon Docker en la sesión) |
| CI | Definido en `.github/workflows/ci.yml`; **pendiente de primera ejecución en GitHub** |

## Verificación realizada

Ejecutado en esta sesión contra PostgreSQL 16.15 y Redis 7.0.15 locales:

- **Backend:** `ruff check` sin errores; **58/58 pruebas** de pytest (autenticación, libro mayor, concurrencia con 20 hilos, inmutabilidad y CHECK en BD, generación, worker, reintentos acotados, reconciliación, URL firmada, aislamiento entre usuarios, administración, presupuestos, valores por defecto seguros y límite de peticiones).
- **Migraciones:** `upgrade head → downgrade base → upgrade head` correcto sobre base de test.
- **API y worker:** `/v1/health` y `/v1/health/ready` con BD y Redis en `ok`; worker arranca y consume la cola.
- **Frontend:** `tsc --noEmit` sin errores; **10/10** pruebas de vitest (paridad de claves es/en, validación, formato); build de producción de Next.js correcto.
- **E2E en navegador** (build de producción, worker real, cola Redis): registro → concesión de créditos por admin → generación → estado "Completada" → WAV válido descargado con URL firmada → saldo 20 → 19 sin reservas pendientes.
- **Responsive:** landing a 390 px sin desbordamiento horizontal.

## Decisiones tomadas

- **Auth propia** (scrypt + JWT en cookie) en lugar de Supabase, para no bloquear el desarrollo. Migrar a Supabase Auth requiere aprobación.
- **Proxy de `/v1/*` desde Next.js** al backend: mismo origen para el navegador, cookies sin CORS.
- **Mock de audio** genera WAV sintético determinista; no produce MP3.
- **Paquetes de créditos inactivos** por defecto; precios de ejemplo en `app/seed.py`.
- Validación de email rechaza dominios reservados como `.test`; usar `example.com` en desarrollo.

## Seguridad: puntos a no olvidar

- No commitear `.env`. Las claves de proveedores solo se leen en el backend.
- En `APP_ENV=production` la API no arranca con secretos por defecto, CORS `*` o cookies no seguras.
- Los textos de términos y privacidad son **borradores** sin revisión legal.
