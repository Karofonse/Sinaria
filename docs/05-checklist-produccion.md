# Checklist de seguridad y lanzamiento

Marca cada punto solo con evidencia. Estado a la fecha de esta sesión entre paréntesis.

## Seguridad de la aplicación
- [x] Contraseñas con scrypt y parámetros explícitos (`app/core/security.py`). *Subir N a 2^17 antes de producción.*
- [x] Sesión en cookie `httpOnly`, `SameSite=Lax`, `Secure` obligatoria en producción (validación de configuración).
- [x] Autorización por propietario en pistas y generaciones; respuesta 404 para recursos ajenos (probado).
- [x] Roles verificados en el servidor; 403 genérico (probado en rutas admin).
- [x] Suspensión inmediata: una sesión abierta deja de funcionar (probado).
- [x] Protección CSRF básica: mutaciones con cuerpo exigen `application/json` (probado).
- [x] CORS con lista explícita; `*` rechazado en producción.
- [x] Cabeceras: `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, HSTS en producción; CSP en el frontend.
- [x] Descargas con URL firmada (HMAC, propietario y caducidad); manipulación y caducidad probadas.
- [x] Validación de entrada con Pydantic `extra="forbid"` y límites de longitud.
- [x] Errores sin trazas al cliente.
- [ ] Rate limiting en Redis probado en una prueba; falta prueba de carga y revisión de los límites reales.
- [ ] **Recuperación de contraseña y verificación de correo: no implementadas.**
- [ ] Refresco de sesión y revocación por `jti` (solo hay expiración de 15 min).
- [ ] Filtro de contenido de prompts y reporte de contenido abusivo.
- [ ] Revisión de dependencias (`pip-audit`, `npm audit`) en CI. *Pendiente de añadir.*
- [ ] Revisión de seguridad externa / pentest.
- [ ] Cabecera CSP sin `unsafe-inline` (requiere nonces de Next.js).

## Dinero y créditos
- [x] Saldo nunca enviado por el cliente; el servidor calcula precios y reservas.
- [x] Libro mayor inmutable (trigger) y saldos con CHECK ≥ 0 (probado).
- [x] Idempotencia de reserva, consumo, liberación y ajuste (probado).
- [x] Concurrencia: 20 hilos sobre 10 créditos → exactamente 10 reservas (probado).
- [x] Invariante billetera = suma del libro mayor (probado).
- [x] Presupuesto diario global y por usuario (probado).
- [ ] **Webhook de Wompi con verificación de checksum: no implementado.**
- [ ] Reembolsos y contracargos en el flujo de pagos: no implementados (solo tipos en el libro mayor).
- [ ] Política de deuda por contracargo sin saldo (decisión de negocio pendiente).
- [ ] Conciliación automática de pagos con el proveedor.

## Operación
- [x] Logs JSON con `request_id`; sin contraseñas ni tokens en logs.
- [x] `/v1/health` (liveness) y `/v1/health/ready` (BD y Redis).
- [x] Reconciliador de trabajos estancados y pendientes (probado).
- [ ] Métricas Prometheus y alertas (tasa de fallos, jobs estancados, diferencias de conciliación).
- [ ] Runbook de incidentes.
- [ ] Prueba de restauración de copia de seguridad.

## Legal y producto
- [ ] Términos y política de privacidad revisados por abogado (los textos actuales son **borradores**).
- [ ] Licencia de la música generada confirmada por modelo y tier de cada proveedor.
- [ ] Plazos de retención fiscal confirmados.
- [ ] Derecho de supresión: procedimiento de borrado de cuenta (no implementado).
- [ ] Precios y paquetes definidos por el propietario (actualmente inactivos).

## Despliegue
- [x] Dockerfiles escritos (**sin construir**: sin daemon Docker en la sesión).
- [x] `docker-compose.yml` de desarrollo escrito (**sin ejecutar**).
- [x] CI con pruebas y build (**pendiente de primera ejecución en GitHub**).
- [ ] Entornos sandbox y prod creados, con secretos en el gestor del proveedor.
- [ ] Dominio, certificados y CORS definitivos.
