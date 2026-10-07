# Roadmap de Vigilia

Estado revisado el **7 de octubre de 2026**, después de la migración a `src/vigilia`. Este es el único roadmap vigente. [README](README.md) explica la operación local; [VIGILIA_FLOW](VIGILIA_FLOW.md) describe el comportamiento implementado.

## Implementado

- [x] Arquitectura con dominio, aplicación, adaptadores y bootstrap; persistencia async con SQLAlchemy/psycopg.
- [x] Tres procesos independientes: API, publicador outbox y worker.
- [x] Ingesta Grafana autenticada con HMAC, normalización y deduplicación persistente.
- [x] Outbox transaccional con claims expiran, tokens y reintento exponencial.
- [x] Eventos v1 y consumer idempotente; offset confirmado tras el efecto durable.
- [x] Correlación determinista por servicio/fingerprint, advisory lock, severidad y revisión de incidente.
- [x] Investigaciones por HTTP con 202, Location e Idempotency-Key; unicidad de trabajo activo por revisión/analizador.
- [x] Leases, fencing tokens, intentos, estados terminales y reintentos diferidos por outbox.
- [x] Simulador y adaptador LiteLLM con salida estructurada, citas verificadas y errores normalizados.
- [x] Telemetría por intento exitoso: proveedor/modelo, tokens, coste estimado, ID de respuesta y latencia.
- [x] RAG explícito de texto/runbooks con embeddings, chunking, reemplazo y borrado de documentos.
- [x] Recuperación exacta pgvector por servicio/entorno/modelo/dimensiones y límites de contexto.
- [x] Persistencia de evidencias y fragmentos recuperados para auditoría.
- [x] Consola de escritorio en inglés: resumen, incidentes, alertas, investigaciones y conocimiento.
- [x] GET /alerts y GET /knowledge/documents paginados; Bearer en memoria en la consola.
- [x] Compose base y override de desarrollo; migraciones y topics automáticos; volúmenes conservados.
- [x] Make instalado en Windows y PATH de usuario configurado; comandos de arranque, logs, migración y comprobación.
- [x] Limpieza del árbol app antiguo, entrypoint redundante, documentación de propuesta y adaptadores legacy sin uso.
- [x] Mantener pip en Docker; pytest se instala solo como dependencia de desarrollo en el host.
- [x] Conservar la cadena Alembic y los informes históricos migrados a investigaciones.
- [x] Actualizar README, flujo, arquitectura y documentación de la consola con el estado real.

## Siguiente bloque: consistencia y presupuesto

Estas tareas tienen prioridad antes de aumentar el uso de proveedores o workers.

- [ ] **Fijar las evidencias a la revisión solicitada.** Hoy se registra `incident_revision` al solicitar, pero el snapshot carga las alertas existentes al reclamar el trabajo. Si llegan alertas mientras está en cola, el contexto puede pertenecer a una revisión posterior. Persistir el snapshot al solicitar o reconstruir la revisión exacta y verificar el caso concurrente.
- [ ] Presupuesto global por periodo y reserva previa de coste, incluyendo generación, embeddings y reintentos.
- [ ] Limitar llamadas simultáneas y solicitudes por cliente; el worker actual procesa mensajes secuencialmente por instancia, pero varias réplicas pueden consumir a la vez.
- [ ] Catálogo de modelos aprobados por entorno, límites de contexto y contabilización de llamadas fallidas.
- [ ] Validar generación estructurada y embeddings contra un proveedor real con gasto acotado (presupuesto de desarrollo acordado: 4–5 €).

## Operación y observabilidad

- [ ] Métricas de ingesta, correlación, lag, edad del outbox, investigaciones, reintentos, coste y latencia.
- [ ] Alertas para outbox retrasado, workers sin progreso e intentos agotados.
- [ ] Vista/comando de operador para fallos permanentes, eventos inválidos y reejecución controlada.
- [ ] Propagar y comprobar IDs de correlación de extremo a extremo; el sobre ya contiene los campos, pero falta trazabilidad operativa completa.
- [ ] Validar reinicios, leases vencidos y concurrencia con múltiples workers y broker real.
- [ ] Adaptar los entrypoints de host para psycopg async en Windows (Selector event loop); Docker funciona en Linux.
- [ ] Revisar la diferencia de collation del volumen PostgreSQL existente antes de actualizar imagen o reconstruir índices.
- [ ] Definir retención/archivo del outbox, eventos procesados, resultados e intentos.
- [ ] Política de cancelación o expiración de investigaciones.
- [ ] Validar configuración HMAC con Grafana real y publicar el ejemplo de contact point.

## Conocimiento y consola

- [ ] Evaluar recuperación y fundamentación con un corpus pequeño de incidentes y runbooks.
- [ ] Versionar la política de chunking/contexto cuando cambie su comportamiento.
- [ ] Medir corpus y latencia antes de introducir HNSW, búsqueda híbrida o reranking.
- [ ] Incorporar una fuente automática de conocimiento solo cuando exista un corpus real (Git/wiki).
- [ ] Decidir si la ingesta de documentos necesita trabajos durables; actualmente ocurre dentro de la petición HTTP.
- [ ] Paginar incidentes y obtener totales desde la API cuando el volumen supere el uso local.
- [ ] Validar navegación, polling, errores y accesibilidad de la consola; diseño móvil si se incorpora al alcance.

## Despliegue y seguridad

- [ ] Separar secretos por proceso: generación solo en el worker, embeddings donde se indexa/recupera, autenticación donde se valida.
- [ ] Gestionar credenciales con el mecanismo del entorno y sustituir las credenciales de desarrollo.
- [ ] TLS y configuración de exposición de /docs y /openapi.json.
- [ ] Política de autenticación/roles y auditoría de comandos para uso multiusuario.
- [ ] Copias de seguridad PostgreSQL y procedimiento probado de restauración.
- [ ] Elegir hosting y límites operativos; Docker Compose sigue siendo un stack local.
- [ ] Coordinar rangos de requirements.txt (pip/Docker) y uv.lock (host), o generar requirements fijados si se necesita reproducibilidad idéntica.

## Cobertura y validación pendiente

La suite actual cubre salud, autenticación, webhook/normalización y publicación de un lote outbox: **8 tests existentes**. No equivale a cobertura completa de la arquitectura. El script `make smoke` comprueba contra Docker el flujo de alerta duplicada, correlación, investigación idempotente, consulta y resolución, con simulador y RAG apagado.

- [ ] Tests de reglas de dominio: ventana, severidad, resolución y correlación concurrente.
- [ ] Tests de investigaciones: revisión, unicidad, leases, fencing, reintentos y fallos permanentes.
- [ ] Tests de contratos LLM y embeddings con proveedores simulados, sin red ni consumo real.
- [ ] Tests de repositorios/migraciones con PostgreSQL: base vacía y actualización con informes históricos.
- [ ] Tests de aislamiento del conocimiento, reemplazo/borrado y validación de citas RAG.
- [ ] Integración con broker: duplicados, caída tras publicar, reinicio y mensajes inválidos.
- [ ] Evaluación controlada de RAG y salida LLM; comprobación de la consola en navegador.

La validación manual de este cierre y sus límites se documentan en [docs/validation.md](docs/validation.md). Las ampliaciones de tests y evaluación siguen siendo un bloque específico pendiente; ejecutar los tests existentes y el smoke forma parte de comprobar este mantenimiento.
