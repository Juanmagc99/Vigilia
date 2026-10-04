# Vigilia

Vigilia is a backend for receiving operational alerts, correlating them into incidents, and running durable incident investigations. Investigations can use the deterministic simulator or a provider-agnostic LLM adapter through LiteLLM. Optional RAG retrieval adds operational documents to an investigation as auditable evidence.

## Architecture

The Python package lives under `src/vigilia` and follows this dependency direction:

```text
HTTP / Grafana / PostgreSQL / Redpanda adapters
                       |
                       v
              application use cases
                       |
                       v
                 domain rules

bootstrap composes the implementations for each process
```

The runtime consists of three application processes:

- `vigilia.main`: FastAPI ingestion, commands, and queries.
- `vigilia.publisher`: reliable PostgreSQL outbox publisher.
- `vigilia.worker`: alert correlation and investigation handlers.

PostgreSQL owns business state and the outbox. Redpanda provides at-least-once delivery. Events are deduplicated by consumer and event ID in the same transaction as their business effect.

## Current flows

```text
Grafana -> API -> alerts + outbox -> publisher -> Redpanda
        -> worker -> incident + revision

Client -> POST investigation -> investigation + outbox -> publisher
       -> worker -> lease + attempt -> configured analyzer -> durable result
       -> GET investigation
```

The simulator performs no external calls and does not infer a probable cause. The LiteLLM analyzer requests a structured `incident_investigation.v1` result, rejects unknown evidence references, and records provider, model, token usage, estimated cost, response ID, and latency for every successful attempt. Incidents without enough evidence can produce `insufficient_evidence` as a valid completed result.

## Local setup

Requirements:

- Python 3.13
- uv
- Docker with Compose

Create the local configuration:

```bash
cp .env.example .env
```

Set distinct values for `VIGILIA_GRAFANA_WEBHOOK_HMAC_SECRET` and `VIGILIA_API_TOKEN`.

Install the package and start infrastructure:

```bash
uv sync
docker compose -f docker/docker-compose.dev.yaml up --build
```

The development stack applies Alembic migrations, initializes the Redpanda topics,
and then starts the API and workers. Existing alerts, incidents, outbox events, and
reports are retained. Historical reports are copied into completed investigations
while the original table remains read-only.

To enable RAG locally, configure `VIGILIA_RAG_ENABLED=true` and
`VIGILIA_RAG_EMBEDDING_MODEL` in `.env`. If generation and embeddings use the same
provider, the embedding adapter reuses `VIGILIA_LLM_API_KEY`; otherwise configure
`VIGILIA_RAG_EMBEDDING_API_KEY`. The sample runbooks can then be indexed with:

```bash
uv run python scripts/seed_knowledge.py
```

This sends only the fictional documents in `scripts/runbooks/` to the embedding
provider. Re-running the command replaces the same three documents in place. See
[`docs/rag.md`](docs/rag.md) for retrieval scope and configuration details.

For host execution against containerized PostgreSQL and Redpanda:

```bash
uv run alembic upgrade head
uv run uvicorn vigilia.main:create_app --factory --reload
uv run vigilia-worker
uv run vigilia-publisher
```

## Configuration

All configuration uses the `VIGILIA_` prefix. Important settings are documented in `.env.example`.

| Setting | Default | Purpose |
| --- | --- | --- |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | local PostgreSQL | Database connection |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:19092` | Redpanda connection |
| `ALERTS_RECEIVED_TOPIC` | `alerts.received.v1` | Versioned alert events |
| `LEGACY_ALERTS_RECEIVED_TOPIC` | `alerts.received` | Migration compatibility |
| `INVESTIGATIONS_REQUESTED_TOPIC` | `investigations.requested.v1` | Investigation jobs |
| `INVESTIGATION_MAX_ATTEMPTS` | `3` | Attempt limit |
| `INVESTIGATION_LEASE_SECONDS` | `120` | Worker claim lifetime |
| `INVESTIGATION_RETRY_MAX_DELAY_SECONDS` | `60` | Retry backoff cap |
| `INVESTIGATION_ANALYZER` | `simulated` | Analyzer implementation: `simulated` or `litellm` |
| `LLM_MODEL` | none | LiteLLM model identifier such as `provider/model` |
| `LLM_API_KEY` | none | Optional generic credential passed to LiteLLM |
| `LLM_API_BASE` | none | Optional compatible endpoint or local model base URL |
| `LLM_TIMEOUT_SECONDS` | `45` | Provider call deadline |
| `LLM_MAX_OUTPUT_TOKENS` | `1200` | Maximum generated tokens per attempt |
| `LLM_MAX_ALERTS` | `50` | Maximum recent alerts sent to the model |
| `RAG_ENABLED` | `false` | Enable document ingestion and knowledge retrieval |
| `RAG_EMBEDDING_MODEL` | none | LiteLLM embedding model; required when RAG is enabled |
| `RAG_EMBEDDING_API_KEY`, `RAG_EMBEDDING_API_BASE` | none | Optional embedding-provider credentials and endpoint |
| `RAG_EMBEDDING_BATCH_SIZE` | `64` | Chunks per embedding request |
| `RAG_CHUNK_SIZE`, `RAG_CHUNK_OVERLAP` | `2400`, `300` | Document chunking limits in characters |
| `RAG_MAX_DOCUMENT_CHARACTERS` | `250000` | Maximum indexed document size |
| `RAG_TOP_K` | `5` | Maximum knowledge chunks retrieved per investigation |
| `RAG_MAX_CONTEXT_CHARACTERS` | `16000` | Maximum retrieved text added to an analysis |
| `GRAFANA_WEBHOOK_HMAC_SECRET` | none | Grafana request authentication |
| `API_TOKEN` | none | Incident API Bearer authentication |

The default remains `simulated`, so local infrastructure and API flows do not consume model tokens. To enable a provider, set `VIGILIA_INVESTIGATION_ANALYZER=litellm` and `VIGILIA_LLM_MODEL`. Credentials may use the generic `VIGILIA_LLM_API_KEY` or provider-specific environment variables recognized by LiteLLM. Only the worker constructs and invokes the real analyzer; the HTTP API never receives an LLM client.

## API

| Method | Endpoint | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | Public | Process liveness |
| `GET` | `/ready` | Public | PostgreSQL readiness |
| `POST` | `/webhooks/grafana` | Grafana HMAC | Ingest alerts and queue events |
| `GET` | `/incidents` | Bearer | List incidents |
| `GET` | `/incidents/{id}` | Bearer | Incident detail and alert timeline |
| `POST` | `/incidents/{id}/investigations` | Bearer | Queue an investigation and return `202` |
| `GET` | `/investigations/{id}` | Bearer | Investigation state and result |
| `GET` | `/incidents/{id}/investigations` | Bearer | Investigation history |
| `GET` | `/incidents/{id}/reports` | Bearer | Deprecated historical report view |

`POST /incidents/{id}/investigations` accepts an optional `Idempotency-Key` header and returns the polling URL in `Location`. Only one investigation can be active for the same incident revision and analyzer version.

The previous blocking `POST /incidents/{id}/report` endpoint no longer exists.

When RAG is enabled, `POST /knowledge/documents` ingests or replaces a Markdown/text
document and `DELETE /knowledge/documents/{document_id}` removes it from future
retrieval. Both require the API Bearer token. See [the detailed RAG guide](docs/rag.md)
for request format, configuration, reindexing, privacy and retrieval behavior.

## Reliability model

- Business writes and outbox events share one database transaction.
- Outbox rows use expiring claims and exponential publication retry.
- Consumers commit Kafka offsets only after a durable effect.
- Event processing is idempotent through `processed_events`.
- Investigation work is claimed with an expiring lease and attempt token.
- A stale worker cannot overwrite a newer attempt.
- Transient analysis failures are rescheduled through a delayed outbox event.

See [docs/architecture.md](docs/architecture.md) for the complete module map,
transaction boundaries, alert-to-investigation flows and failure model. [The RAG
guide](docs/rag.md) covers document ingestion, embeddings, retrieval, and audit data.
