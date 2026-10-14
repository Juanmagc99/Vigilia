# Límites de solicitudes y concurrencia

Vigilia aplica cuotas HTTP compartidas mediante Redis, un límite durable de investigaciones activas en PostgreSQL y plazas compartidas para generación y embeddings. Los mensajes de rechazo, errores y logs están en inglés.

## Valores iniciales

| Control | Variable `VIGILIA_` | Valor | Alcance |
| --- | --- | --- | --- |
| Entrada HTTP | `RATE_LIMIT_INGRESS_PER_MINUTE` | 120/min | IP de conexión, antes de autenticación |
| API protegida | `RATE_LIMIT_API_PER_MINUTE` | 60/min | Bearer válido, todas las rutas protegidas |
| Solicitar investigación | `RATE_LIMIT_INVESTIGATIONS_PER_MINUTE` | 5/min | Bearer válido, todos los incidentes |
| Indexar conocimiento | `RATE_LIMIT_KNOWLEDGE_PER_MINUTE` | 2/min | Bearer válido |
| Webhook Grafana | `RATE_LIMIT_WEBHOOKS_PER_MINUTE` | 120/min | Integración, después de verificar HMAC |
| Investigaciones activas | `MAX_ACTIVE_INVESTIGATIONS` | 2 | Toda la base PostgreSQL |
| Llamadas al generador | `LLM_MAX_CONCURRENT_CALLS` | 2 | Workers del mismo entorno |
| Llamadas a embeddings | `RAG_EMBEDDING_MAX_CONCURRENT_CALLS` | 2 | API/workers del mismo entorno |

Las cuotas usan una ventana deslizante de 60 segundos. Investigación e indexación consumen también la cuota general y la de entrada. Se cuentan intentos, incluidos errores de validación y peticiones idempotentes. La autenticación se valida antes de consumir la cuota del Bearer o de Grafana; una petición no autenticada solo consume cuota de entrada.

Actualmente hay un solo Bearer: todos sus usuarios comparten cuota. Cambiar el ID de incidente o la clave de idempotencia no evita el límite. Las claves Redis contienen hashes de identidades, nunca el token original. Cuotas y plazas se agrupan por `VIGILIA_ENVIRONMENT`; todas las réplicas deben usar el mismo Redis, entorno y configuración.

## Respuestas y disponibilidad

Los rechazos de cuota devuelven `429` con el contrato habitual de errores: código `rate_limit_exceeded`, mensaje `Too many requests. Please try again later.` y metadatos de la cuota. `Retry-After` indica los segundos hasta que puede liberarse cuota. `X-RateLimit-Limit`, `X-RateLimit-Remaining` y `X-RateLimit-Reset` (timestamp Unix en segundos) describen la última cuota comprobada. La consola muestra la espera sin repetir automáticamente escrituras.

Si Redis no responde, las operaciones protegidas devuelven `503`, código `rate_limit_backend_unavailable` y `Retry-After: 5`; no se concede tráfico sin comprobar las cuotas. `/ready` comprueba Redis cuando está configurado. `/health`, los assets de la consola y OpenAPI no consumen cuota. Las URLs de conexión y excepciones internas no se devuelven al cliente.

El límite durable cuenta investigaciones `queued`, `running` y `retry_wait`. Un advisory lock PostgreSQL serializa las admisiones y la investigación/outbox se guardan juntos. Un rechazo devuelve `429`, código `investigation_capacity_exceeded` y `Retry-After: 5` como espera sugerida. Una misma `Idempotency-Key` devuelve el trabajo existente incluso con el cupo completo. Los trabajos pendientes siguen ocupando cupo cuando los workers están parados.

## Llamadas a proveedores

Generación y embeddings usan plazas independientes, compartidas entre procesos del mismo entorno. Cada plaza tiene token único y vencimiento mayor que el timeout de la llamada. Un timeout exterior limita la espera y la plaza se libera al terminar o fallar. Tras una caída del proceso, se recupera al vencer. Liberar un token antiguo no elimina una plaza nueva.

Si no hay plaza, el analizador devuelve un error transitorio con una espera sugerida. El worker registra el intento y programa un reintento durable que respeta esa espera y el máximo de intentos existente. La indexación HTTP devuelve `503` y `Retry-After`. LiteLLM no hace reintentos internos de generación ni embeddings. Las plazas limitan peticiones en curso de Vigilia; el presupuesto de dinero y las cuotas de tokens/RPM del proveedor siguen pendientes.

## Configuración local

Compose incorpora Redis con AOF y volumen `redis-data`; publica el puerto solo en `127.0.0.1`. API/worker esperan a su healthcheck. `VIGILIA_REDIS_URL` es `redis://redis:6379/0` en Docker y `redis://127.0.0.1:6379/0` en el host. La IP explícita evita conexiones IPv6 a `localhost` cuando Docker publica solo en IPv4.

`make dev-start` construye y levanta las dependencias. No hacen falta nuevas migraciones. Para cambiar límites, edita las variables en `.env` y recrea API/worker con `make dev-rebuild`.

Las cuotas HTTP se desactivan con `VIGILIA_RATE_LIMIT_ENABLED=false`, las plazas con `VIGILIA_PROVIDER_CALL_LIMITS_ENABLED=false` y el cupo durable con `VIGILIA_MAX_ACTIVE_INVESTIGATIONS=0`. Cuando ambas funciones Redis están desactivadas, Redis deja de ser necesario para la aplicación.

Detrás de un proxy, configura en el servidor ASGI qué proxies son de confianza antes de utilizar IPs reenviadas. El middleware utiliza la IP que proporciona ASGI y no interpreta por su cuenta `X-Forwarded-For`.

## Comprobaciones

Las comprobaciones adicionales usan Redis y un esquema PostgreSQL temporal aislados; las llamadas a proveedores se sustituyen para evitar consumo:

```powershell
$env:VIGILIA_TEST_REDIS_URL = "redis://127.0.0.1:6379/0"
$env:VIGILIA_TEST_POSTGRES = "true"
uv run --locked pytest -q
```

Cubren cuota compartida/atómica, vencimiento, autenticación, cuotas por operación, HMAC, caída de Redis, recuperación de plazas, liberación tras timeout y admisión concurrente con idempotencia/outbox. Sin esas variables, se omiten las comprobaciones de infraestructura.
