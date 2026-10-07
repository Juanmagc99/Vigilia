# Vigilia

Vigilia recibe alertas de Grafana, las correlaciona en incidentes y ejecuta investigaciones durables con evidencias auditables. Incluye una consola web de escritorio en inglés. El análisis puede usar un simulador sin llamadas externas o LiteLLM; RAG añade documentación operacional mediante PostgreSQL/pgvector.

## Arquitectura actual

El paquete instalado vive en `src/vigilia`. La dirección de dependencias es `adaptadores -> aplicación -> dominio`; `bootstrap` construye y cierra los recursos de cada proceso.

| Proceso | Entrada | Responsabilidad |
| --- | --- | --- |
| API | `vigilia` / `vigilia.main:create_app` | Webhooks, comandos, consultas, ingesta de conocimiento y `/ui/` |
| Publicador | `vigilia-publisher` | Publicar el outbox de PostgreSQL en Redpanda |
| Worker | `vigilia-worker` | Correlación y ejecución de investigaciones |

```text
Grafana -> API -> alertas + outbox -> publicador -> alerts.received.v1
        -> worker -> incidente + revisión

Consola/cliente -> POST investigación -> investigación + outbox
               -> publicador -> investigations.requested.v1 -> worker
               -> snapshot + RAG opcional -> analizador -> resultado durable
               -> GET investigación
```

PostgreSQL es la fuente de verdad. Redpanda entrega al menos una vez: los consumidores deduplican los eventos y confirman offsets después de guardar su efecto. Los leases y tokens de intento protegen las investigaciones de escrituras de workers obsoletos.

Lee [el flujo completo](VIGILIA_FLOW.md), [la arquitectura](docs/architecture.md), [la guía RAG](docs/rag.md), [la consola](docs/web-console.md) y [el roadmap vigente](VIGILIA_ROADMAP.md).

## Arranque local

Requisitos: Docker Engine con Compose, Python 3.13, [uv](https://docs.astral.sh/uv/) y GNU Make para los atajos. Docker usa pip con `requirements.txt`. En el host, `uv sync --locked` instala el paquete desde `pyproject.toml` y `uv.lock`, además de pytest para desarrollo. Al cambiar dependencias de ejecución, actualiza también `requirements.txt`.

En PowerShell:

```powershell
Copy-Item .env.example .env
# Edita .env y sustituye los dos secretos por valores distintos.
uv sync --locked
make dev-start
```

En Linux/macOS, copia la configuración con `cp .env.example .env`. El arranque aplica Alembic y crea los topics antes de iniciar los consumidores. Los volúmenes existentes se conservan.

- Consola: <http://localhost:8000/ui/>
- OpenAPI: <http://localhost:8000/docs>
- Grafana local: <http://localhost:3000> (`admin` / `admin` en desarrollo).

La consola solicita `VIGILIA_API_TOKEN`, lo guarda solo en memoria y vuelve a pedirlo al recargar. Se sirve desde la API, sin npm ni proceso frontend separado.

### Comandos del proyecto

| Comando | Efecto |
| --- | --- |
| `make help` | Mostrar los comandos disponibles |
| `make dev-start` | Construir y arrancar todo en segundo plano |
| `make dev-restart` | Reiniciar API, worker y publicador |
| `make dev-rebuild` | Reconstruir aplicación, aplicar migraciones y recrear procesos |
| `make dev-stop` | Parar contenedores conservando datos |
| `make dev-status` | Mostrar contenedores, incluidos los inicializadores terminados |
| `make dev-logs` | Seguir logs; salir con Ctrl+C |
| `make dev-migrate` | Aplicar migraciones pendientes |
| `make test` | Ejecutar los tests existentes |
| `make smoke` | Probar alerta, duplicado, correlación, investigación y resolución |
| `make seed-knowledge` | Indexar los tres runbooks ficticios; consume embeddings |

En Windows puedes instalar Make con:

```powershell
winget install --id GnuWin32.Make --exact
```

Añade `C:\Program Files (x86)\GnuWin32\bin` al PATH de usuario y abre una terminal nueva. En este equipo ya está instalado, el PATH de usuario está configurado y un lanzador en `~/.local/bin` permite usar `make` también desde las terminales actuales. Si una terminal que estaba abierta no lo encuentra, ejecuta `& 'C:\Program Files (x86)\GnuWin32\bin\make.exe' help` o reiníciala.

Los comandos Docker equivalentes usan **ambos** archivos:

```bash
docker compose -f docker/docker-compose.yaml -f docker/docker-compose.dev.yaml up --build -d
```

`docker-compose.yaml` contiene los servicios compartidos y puede arrancar por sí solo; `docker-compose.dev.yaml` añade montajes de código y recarga de la API. Los puertos se publican en loopback. Este stack sigue siendo local: el despliegue productivo está pendiente.

### Prueba completa sin consumo de API

Configura `VIGILIA_INVESTIGATION_ANALYZER=simulated` y `VIGILIA_RAG_ENABLED=false` en `.env`, ejecuta `make dev-rebuild` y después `make smoke`. La prueba utiliza los servicios reales y deja un incidente sintético resuelto con un servicio único `smoke-*`. No borra datos existentes.

Para enviar alertas manualmente, el script carga el secreto desde `.env`:

```bash
uv run --locked python scripts/send_grafana_alert.py --service payments-api --status firing --severity critical --alert-name HighCPU
uv run --locked python scripts/send_grafana_alert.py --service payments-api --status resolved --severity critical --alert-name HighCPU
```

### Ejecutar procesos desde el host en Linux/macOS

En Windows utiliza los procesos Docker: los entrypoints de host aún necesitan adaptar el event loop para psycopg async. En Linux/macOS, arranca solo PostgreSQL, Redpanda y el inicializador de topics; ejecuta cada proceso en su terminal. Mantén `VIGILIA_ENVIRONMENT` consistente con el corpus RAG y usa las direcciones locales de `.env.example`.

```bash
docker compose -f docker/docker-compose.yaml up -d postgres redpanda topics-init
uv run --locked alembic upgrade head
uv run --locked vigilia --reload
uv run --locked vigilia-worker
uv run --locked vigilia-publisher
```

## Configuración

Todas las opciones propias usan `VIGILIA_`. [.env.example](.env.example) contiene los valores y límites configurables.

| Grupo | Opciones principales |
| --- | --- |
| Persistencia | `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` |
| Mensajería | `KAFKA_BOOTSTRAP_SERVERS`, `ALERTS_RECEIVED_TOPIC`, `INVESTIGATIONS_REQUESTED_TOPIC` |
| Correlación | `INCIDENT_CORRELATION_WINDOW_MINUTES` (45) |
| Investigaciones | `INVESTIGATION_MAX_ATTEMPTS` (3), `INVESTIGATION_LEASE_SECONDS` (120), `INVESTIGATION_RETRY_MAX_DELAY_SECONDS` (60) |
| Analizador | `INVESTIGATION_ANALYZER` (`simulated` por defecto), `LLM_MODEL`, `LLM_API_KEY`, `LLM_API_BASE` |
| Límites LLM | `LLM_TIMEOUT_SECONDS` (45), `LLM_MAX_OUTPUT_TOKENS` (1200), `LLM_MAX_ALERTS` (50) |
| Conocimiento | `RAG_ENABLED` (`false`), `RAG_EMBEDDING_MODEL`, `RAG_EMBEDDING_API_KEY`, `RAG_EMBEDDING_API_BASE` |
| Contexto RAG | `RAG_TOP_K` (5), `RAG_MAX_CONTEXT_CHARACTERS` (16000), límites de documentos y fragmentos |
| Seguridad | `GRAFANA_WEBHOOK_HMAC_SECRET`, `GRAFANA_WEBHOOK_MAX_AGE_SECONDS` (300), `API_TOKEN` |

Para generación real, configura `litellm` y un modelo compatible con JSON Schema. Solo el worker llama al modelo de generación. Si activas RAG, la API llama al proveedor de embeddings al indexar documentos y el worker al preparar la consulta semántica. Las claves de embeddings pueden reutilizar `LLM_API_KEY` cuando el proveedor es el mismo. El simulador con RAG activado también puede consumir embeddings.

El adaptador valida las citas contra los IDs enviados y persiste modelo, tokens, coste estimado y latencia por intento exitoso. `insufficient_evidence` es un resultado válido. Las hipótesis requieren comprobación humana.

## API y consola

| Método | Ruta | Autenticación | Función |
| --- | --- | --- | --- |
| GET | `/health`, `/ready` | Pública | Proceso y conexión PostgreSQL |
| GET | `/ui/` | Estáticos públicos | Consola; los datos requieren Bearer |
| POST | `/webhooks/grafana` | HMAC + timestamp | Persistir alertas y outbox; devolver 202 |
| GET | `/alerts` | Bearer | Eventos paginados, filtrados por servicio/estado |
| GET | `/incidents`, `/incidents/{id}` | Bearer | Incidentes y detalle con alertas |
| POST | `/incidents/{id}/investigations` | Bearer | Solicitar investigación; devolver 202 y `Location` |
| GET | `/investigations/{id}`, `/incidents/{id}/investigations` | Bearer | Estado, resultado, intentos e historial |
| GET | `/knowledge/documents` | Bearer | Metadatos paginados del entorno configurado |
| POST | `/knowledge/documents` | Bearer | Indexar/reemplazar texto; requiere RAG |
| DELETE | `/knowledge/documents/{id}` | Bearer | Retirar un documento del índice |

Las páginas de alertas y conocimiento devuelven `items`, `total`, `limit` y `offset`, con máximo 100 elementos. El comando de investigación admite `Idempotency-Key`; solo puede haber una investigación activa por incidente, revisión y versión del analizador. La ingesta de documentos es síncrona durante la petición, no un trabajo en Kafka.

## Migración y mantenimiento

Se retiraron el árbol `app/` antiguo (solo quedaban cachés), el entrypoint raíz redundante, la suscripción al topic sin versión y la API antigua de informes. Usa los entrypoints instalados, los eventos `*.v1` y las investigaciones. Antes de actualizar otra instalación, drena sus eventos del topic antiguo y comprueba que no queden outbox antiguos pendientes.

La cadena Alembic y la tabla archivada `reports` se conservan: permiten actualizar bases existentes sin perder historial. La migración durable copia sus informes como investigaciones completadas con esquema `legacy_report.v1`; se consultan por la API de investigaciones. El frontend muestra ese esquema histórico en formato JSON. No elimines migraciones ya aplicadas ni ejecutes `down -v` si quieres conservar datos.

Las comprobaciones realizadas y sus límites están en [docs/validation.md](docs/validation.md). Para diagnosticar el entorno: `make dev-status`, `make dev-logs`, `GET /ready`, estado de `migrate`/`topics-init`, filas pendientes en `outbox_events` y estados/intentos de `investigations`. La suite actual es pequeña; el roadmap identifica la cobertura y las comprobaciones operativas pendientes.
