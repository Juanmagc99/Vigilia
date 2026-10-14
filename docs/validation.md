# Validación del mantenimiento

## Límites de solicitudes y concurrencia: 14 de octubre de 2026

- Suite con Redis y PostgreSQL locales: **17 comprobaciones pasan**, incluidas cuota atómica entre clientes, expiración, autenticación, rutas costosas, HMAC, Redis no disponible, recuperación de plazas, timeout de proveedor y admisión concurrente de investigaciones con idempotencia/outbox. La comprobación PostgreSQL utiliza un esquema temporal aislado.
- API real en un contenedor temporal con cuota de 2/min y espacio Redis propio: lectura sin credenciales `401`, dos lecturas autenticadas `200` y siguiente lectura `429` con `Retry-After` y cabeceras de cuota. `/health` y `/ready` siguen respondiendo `200`. El contenedor se retiró y la cuota de la API habitual se conservó.
- Compose validado; imagen reconstruida y API, worker, publicador, PostgreSQL, Redpanda y Redis arrancados. Revisión estática de los módulos modificados sin errores.
- Las comprobaciones no llamaron a proveedores reales: generación se sustituyó y la comprobación HTTP temporal usó lecturas con RAG apagado. El stack habitual conserva su configuración RAG.

La advertencia existente de Starlette/httpx continúa. Estas comprobaciones no prueban presupuestos de dinero, cuotas de tokens/RPM del proveedor ni calidad RAG. Configuración y alcance en [rate-limits.md](rate-limits.md).

## Mantenimiento anterior

Validación local del 7 de octubre de 2026. Docker mantuvo pip y requirements.txt. Las comprobaciones no llamaron a proveedores de generación ni embeddings.

## Comprobaciones completadas

- `make test`: 8 tests existentes pasan. Starlette emite una advertencia de deprecación sobre el cliente httpx; no impide la ejecución.
- Construcción de la imagen con pip y arranque del stack de desarrollo. PostgreSQL, Redpanda y API responden; migrate y topics-init terminan con código 0.
- Smoke contra API, outbox, broker y worker: HMAC, rechazo de lectura sin Bearer, alerta duplicada, correlación, revisión, solicitud idempotente, investigación completada con evidencia, historial y resolución. Se repitió usando alerts.received.v1 después de actualizar la configuración local del topic.
- Validación de persistencia en una base temporal: cadena Alembic desde la base inicial hasta head, carga de un informe histórico y copia a investigación completada legacy_report.v1.
- Con pgvector real y embeddings deterministas locales: reemplazo del mismo documento, fragmentación, paginación, filtrado por servicio/entorno, recuperación, redacción de un secreto ficticio y borrado. La base temporal se retiró al terminar.
- Contrato Kafka: aceptación del sobre v1 y rechazo del antiguo mensaje sin sobre.
- Construcción del wheel con los seis assets de la consola incluidos.
- Revisión en navegador de acceso, navegación, incidente, investigación, alertas y conocimiento. Se corrigió la interpretación de fechas UTC de las columnas históricas sin offset.
- Validación de ambos Compose y revisión de diferencias sin errores de whitespace.

Las alertas e investigaciones sintéticas quedan en la base local como incidentes resueltos con servicio smoke-*. Se conservan los datos y volúmenes anteriores. El árbol app antiguo contenía solo 87 cachés .pyc; se archivó fuera del repositorio en la carpeta temporal del usuario.

## Límites observados

No se ejecutaron generación ni embeddings reales, pruebas de carga, fallos del proveedor, recuperación concurrente de leases ni una evaluación de calidad RAG. Las comprobaciones manuales de persistencia no sustituyen una suite automatizada de integración.

El volumen PostgreSQL existente avisa de una diferencia de versión de collation (2.41 frente a 2.36). No se modificaron índices ni metadata de la base del usuario; la validación de migraciones usó una base temporal creada desde template0. Queda revisar y corregir la compatibilidad de la imagen con el volumen existente de forma planificada.

En Windows, psycopg async exige un event loop Selector; los entrypoints de host todavía usan el loop predeterminado. La validación temporal de persistencia configuró Selector explícitamente. Los procesos de Docker se ejecutan en Linux y el flujo probado funciona allí. Para el uso local habitual en Windows, utiliza Make/Docker.

El roadmap conserva como pendiente ampliar tests, validar proveedores reales y fijar estrictamente la evidencia a la revisión solicitada.
