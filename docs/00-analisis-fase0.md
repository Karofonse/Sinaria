# Fase 0 — Análisis de requisitos, proveedores, licencias, riesgos y costos

Estado de verificación: **parcial**. Este entorno no pudo resolver `fal.ai` ni `docs.wompi.co` (la red de la sesión no permite esos dominios). Todo dato marcado como **[VERIFICAR]** procede de búsquedas de terceros o de resúmenes no oficiales y requiere confirmación humana contra la documentación oficial antes de activar cualquier integración real.

## 1. Requisitos clave

| Área | Requisito | Decisión de diseño |
|---|---|---|
| Créditos | Saldo nunca enviado por el navegador; libro mayor inmutable | Ledger append-only en PostgreSQL con triggers que bloquean UPDATE/DELETE y saldos en `wallets` con `CHECK >= 0` |
| Pagos | Créditos solo tras confirmación del proveedor por webhook verificado | Webhook Wompi con verificación de checksum; el retorno del navegador nunca acredita |
| Generación | Reservar → encolar → ejecutar → consumir o liberar | Máquina de estados en `generation_jobs`, transiciones condicionales (`UPDATE … WHERE status = …`) |
| Proveedores | Adaptadores; fal.ai desactivado por defecto | Interfaz `MusicProvider` + `mock` activo por defecto; `fal_stable_audio` existe pero no se invoca sin `FAL_ENABLED=true` y clave |
| Archivos | Descarga en backend/worker → almacenamiento privado propio | Storage con interfaz; `local` en dev, `s3` (R2) en prod; URLs firmadas con caducidad |
| Idioma | Español e inglés preparados | Diccionarios `es`/`en` en el frontend desde el inicio |
| Auth | Supabase (PostgreSQL + auth) | **Decisión pendiente** (ver §5). Implementado: auth propia con JWT para no bloquear el desarrollo |

## 2. Proveedores musicales

### 2.1 fal.ai — Stable Audio 3 Small (adaptador inicial)

- Endpoint de música según búsqueda: `fal-ai/stable-audio-3/small/music/text-to-audio`. [VERIFICAR]
- Variantes encontradas: `small/music/base/text-to-audio` (expone `num_inference_steps` 1–100, default 50; `guidance_scale` 0–25, default 7; `seed` opcional; `bitrate` default `192k`). [VERIFICAR]
- Duración: la página del modelo describe composiciones "de hasta 2 minutos" para Small Music. El parámetro exacto de duración **no** se pudo confirmar. Hasta confirmarlo, el sistema usa un límite configurable (`PROVIDER_MAX_DURATION_S`, por defecto 120 s) y no envía parámetros de duración sin verificación. [VERIFICAR]
- Precio: un agregador lista ~$0.0217 por audio para Small Music. Dato no oficial. [VERIFICAR]
- Modalidad: el SDK `@fal-ai/client` / `fal_client` (Python) usa colas (`submit` / `status` / `result`). Los nombres exactos de métodos del SDK y la política de webhooks de fal **no se pudieron verificar**. El adaptador usará la API de cola solo tras verificación. [VERIFICAR]
- Política de enlaces: los archivos devueltos son temporales; el worker los descarga y guarda en almacenamiento propio (requisito cumplido por diseño).

### 2.2 Stability AI — Stable Audio 3.0 (adaptador preparado, no implementado)

- Hallazgo: existen documentaciones de terceros (WaveSpeedAI) y el modelo Large aparece como propietario disponible vía API de Stability o fal. [VERIFICAR]
- **Conflicto de precios sin resolver**: un rastreador de terceros reporta 26 créditos (~$0.26) por llamada y luego 8 créditos (~$0.08) desde el 23-oct-2026. No confiar en ninguna cifra hasta leer la tarifa oficial de Stability. [VERIFICAR]
- **Licencia comercial**: un blog afirma soporte de uso comercial para los modelos de música; no es una fuente contractual. Requiere revisión legal y lectura de los términos de Stability para el modelo y tier concretos. **Aprobación humana obligatoria.**

### 2.3 Conclusión de proveedores

Se implementa el patrón de adaptadores con tres implementaciones:
1. `mock` — activo por defecto; genera un WAV/MP3 sintético de prueba sin coste. Usado en tests y en desarrollo.
2. `fal_stable_audio_small` — implementado como esqueleto con llamadas bloqueadas por `FAL_ENABLED=false`. No se llama a la red hasta que se verifiquen endpoint, parámetros, SDK y licencia.
3. `stability_stable_audio_3` — solo interfaz/stub, sin llamadas.

## 3. Pagos — Wompi Colombia

- Entorno inicial: sandbox. Credenciales: **ninguna disponible en este entorno**. No se invocan APIs de pago.
- Webhooks: la documentación oficial indica que cada entorno (sandbox y producción) tiene su propia URL de eventos. [VERIFICAR con docs.wompi.co]
- Verificación: según búsqueda, el checksum viaja en el header `X-Event-Checksum` y en `signature.checksum` del cuerpo; se calcula con SHA-256 sobre los valores de `signature.properties`, el `timestamp` y el secreto de eventos (orden exacto **[VERIFICAR]**). El código implementará la verificación con comparación en tiempo constante y rechazará sin procesar si no coincide; el orden de concatenación se contrastará con la documentación y con eventos de prueba del sandbox.
- Idempotencia: cada evento se guarda en `payment_events` con clave única `(provider, provider_event_id)` o, si no existe, un hash del cuerpo. Reprocesar devuelve éxito sin efectos.
- **No se habilitan pagos reales ni generación de enlaces de pago** sin autorización expresa del propietario.

## 4. Costos de referencia (no verificados — orientativos)

| Concepto | Fuente | Estado |
|---|---|---|
| Generación Small Music fal.ai | Agregador | ~$0.0217 / audio [VERIFICAR] |
| Generación Stable Audio 3.0 | Terceros | Conflicto: $0.08 vs $0.26 [VERIFICAR] |
| Infraestructura base (Supabase, Vercel, Render/Railway, R2) | Precios públicos conocidos | Pendiente de cotización real |
| Comisiones Wompi | Pendiente | [VERIFICAR] |

El modelo de créditos se diseña para que el precio por crédito y el coste por generación sean configurables sin cambios de código (`provider_models.credits_per_generation`, `credit_packages`).

## 5. Dependencias externas y acciones humanas requeridas

| # | Acción requerida | Bloquea |
|---|---|---|
| 1 | Permitir `fal.ai` y `docs.wompi.co` en la configuración de red de la sesión | Verificar API de fal y checksum de Wompi |
| 2 | Confirmar duración máxima, parámetros y precio de Stable Audio Small en fal.ai | Fase 4 |
| 3 | Confirmar tarifa oficial y licencia comercial de Stability AI | Adaptador Stability |
| 4 | Decidir auth: Supabase Auth vs. auth propia (ver `01-arquitectura.md` §5) | Fase 2 definitiva |
| 5 | Cuenta Cloudflare R2 (o S3) y bucket privado | Fase 7 en producción |
| 6 | Cuenta Wompi sandbox y URL de eventos | Fase 6 |
| 7 | Términos legales, política de privacidad y retención (texto final) | Lanzamiento |
| 8 | Aprobación de cualquier llamada que consuma créditos reales | Pruebas con proveedor real |

## 6. Riesgos principales

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Doble cobro / doble acreditación | Financiero | Idempotency keys, unicidad en BD, transacciones con bloqueo de fila |
| Webhook falso | Financiero | Verificación de checksum antes de cualquier efecto |
| Proveedor cobra y falla la descarga | Coste | Reconciliación de jobs `processing` estancados, reintentos acotados, `provider_usage` |
| Costos imprevistos | Financiero | Presupuestos por usuario y global diario, precio por modelo configurable, kill-switch por proveedor |
| Licencia de salida musical | Legal | Términos con revisión humana; registro de proveedor y modelo por pista |
| Enlaces temporales del proveedor expiran | Funcional | Descarga inmediata a almacenamiento propio |
| Contenido abusivo / derechos de autor | Legal | Filtro de prompts (pendiente), reporte de contenido, moderación en panel admin |
| Dependencia de terceros no verificados | Técnico | Adaptadores con contrato y tests con mock; fal/Stability desactivados por defecto |
