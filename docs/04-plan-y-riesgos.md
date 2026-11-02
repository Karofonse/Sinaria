# Plan de implementación, riesgos y decisiones pendientes

## 1. Estado al cierre de esta sesión

Verificado en esta sesión (ver `README.md` §Verificación): API y worker arrancan contra PostgreSQL 16 y Redis reales; 58 pruebas de backend pasan (incluidas concurrencia real con hilos y pruebas de inmutabilidad en BD); 10 pruebas de frontend pasan; TypeScript sin errores; build de producción de Next.js correcto; un test E2E en navegador completa el flujo registro → crédito → generación → descarga WAV → consumo de saldo.

NO verificado: Docker Compose (no hay daemon Docker en esta sesión), despliegue real, integraciones externas (fal.ai, Stability, Wompi, Supabase, R2).

## 2. Fases

| Fase | Contenido | Estado real |
|---|---|---|
| 0 | Análisis de requisitos, proveedores, licencias, riesgos | **Hecha**, con verificación externa parcial (`00-analisis-fase0.md`) |
| 1 | Arquitectura, monorepo, modelo de datos, flujos | **Hecha** |
| 2 | Auth (registro, login, logout, `/me`), control por roles, rutas protegidas, frontend base, panel | **Parcial**: falta recuperación de contraseña y verificación de correo (solo existe el texto de la UI y el diseño). Supabase Auth no integrado |
| 3 | Generación con proveedor simulado, worker, estados, reintentos, reconciliación | **Hecha** |
| 4 | Adaptador fal.ai Stable Audio Small | **Esqueleto desactivado.** Sin llamadas reales: falta verificar endpoint, parámetros y SDK |
| 5 | Billetera, libro mayor inmutable, idempotencia, concurrencia | **Hecha** (CHECK, triggers y pruebas en BD). Conciliación automática: solo la invariante verificable por SQL; el reconciliador de jobs está hecho |
| 6 | Wompi sandbox, webhooks | **No implementada.** Hay tablas `payments` y `payment_events` (con trigger que protege el cuerpo y la firma) y `POST /v1/billing/checkout` devuelve 503. **No hay endpoint de webhook ni verificación de checksum**: requiere la documentación oficial de Wompi y credenciales sandbox |
| 7 | Biblioteca, almacenamiento privado, reproductor | **Hecha con almacenamiento local.** Listado, búsqueda por título, renombrado, borrado lógico, URL firmada de 5 min, reproductor. Pendiente: R2/S3 real, MP3 (la salida actual es WAV), búsqueda avanzada y streaming con `Range` |
| 8 | Panel admin, límites, observabilidad | **Parcial**: panel (usuarios, suspensión, ajustes auditados, métricas, precios por modelo, deshabilitar modelos), presupuestos diario global y por usuario. **Pendiente**: Prometheus, alertas, deshabilitar proveedor por tenant y pantallas de pagos |
| 9 | Pruebas, revisión de seguridad, preparación de despliegue | **Parcial**: pruebas automatizadas y E2E ejecutadas; Dockerfiles escritos pero no construidos; revisión de seguridad documentada en `05-checklist-produccion.md` |
| 10 | Checklist de lanzamiento | **Entregado** (`05-checklist-produccion.md`) |

## 3. Riesgos abiertos y decisiones pendientes

### Decisiones que requieren al propietario
1. **Autenticación**: ¿Supabase Auth o auth propia? (Recomendación: Supabase Auth en prod, tras aprobar la migración.)
2. **Proveedor musical principal**: confirmar fal.ai Stable Audio Small y la licencia de salida comercial.
3. **Stability AI**: tarifa oficial (conflicto 8 vs 26 créditos) y términos comerciales.
4. **Modelo de precios**: precio por crédito, paquetes iniciales y coste por generación. Sin datos, `app/seed.py` usa valores de ejemplo y crea los paquetes inactivos.
5. **Contracargos sin saldo**: política de deuda pendiente (ver `02-modelo-datos.md`).
6. **Retención fiscal** de pagos y movimientos: plazo legal aplicable en Colombia (consultar contador/abogado).
7. **Dominio, marca y textos legales**: los textos de términos y privacidad incluidos son **plantillas**, no asesoría legal.
8. **Presupuestos**: cifras iniciales de presupuesto diario global y por usuario.

### Riesgos técnicos
| Riesgo | Mitigación en el código |
|---|---|
| Carrera entre dos reservas del mismo usuario | `SELECT … FOR UPDATE` sobre la wallet + CHECK en BD + test de concurrencia |
| Webhook duplicado o reordenado | Clave única en `payment_events`; transición de `payments` condicional |
| Job encolado dos veces | Transición `pending → processing` condicional; el segundo worker no hace nada |
| Crash entre descarga y commit | Reintento idempotente de descarga; el consumo solo ocurre al guardar la pista |
| Proveedor sin SLA | Timeouts configurables, clasificación de errores, reintentos acotados |
| Enlace temporal de proveedor expira | Descarga inmediata a almacenamiento propio |

## 4. Próximos pasos inmediatos (fuera de esta sesión)
1. Permitir `fal.ai` y `docs.wompi.co` en red de sesión para verificar lo marcado **[VERIFICAR]**.
2. Crear proyectos Supabase `sonaria-sandbox` y `sonaria-prod` y bucket R2 privado.
3. Resolver decisiones §3.1–3.8.
4. Activar Wompi sandbox con credenciales propias y pruebas de webhook con eventos reales de sandbox.
