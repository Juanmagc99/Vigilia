# Vigilia

Vigilia is an incident-intelligence backend for Grafana Alerting. It receives Grafana webhooks, turns raw alerts into normalized records, stores them, and groups related alerts into operational incidents. It can also generate and retain a structured, LLM-powered report for an incident.

Grafana remains responsible for evaluating alert rules. Vigilia provides the operational layer after an alert is raised: persistence, event processing, correlation, incident inspection, and report generation.

## What happens to an alert?

```text
Grafana Alerting
  -> POST /webhooks/grafana
  -> normalize and persist Alert in PostgreSQL
  -> publish alerts.received to Redpanda (Kafka-compatible)
  -> consumer correlates the Alert into an Incident
  -> optional LLM report generation for the Incident
```

An **alert** is one incoming event. An **incident** is a group of related alerts.

- Firing alerts are grouped by service within a configurable time window.
- Resolved alerts are matched to the original alert by Grafana fingerprint.
- An incident resolves only after the latest event for every associated fingerprint is `resolved`.
- Incident severity keeps the highest severity observed: `critical > warning > info > unknown`.

## Architecture

| Component | Responsibility |
| --- | --- |
| FastAPI API | Receives Grafana webhooks, exposes health and incident endpoints, and generates reports on demand. |
| PostgreSQL | Stores alerts, incidents, alert-to-incident links, and generated reports. |
| Redpanda | Kafka-compatible event broker between ingestion and background processing. |
| Consumer | Reads `alerts.received` and applies incident-correlation rules. |
| LiteLLM | Calls the configured LLM provider to produce validated JSON incident reports. |
| Grafana | Optional local Grafana instance for alerting integration and exploration. |

## Quick start with Docker Compose

### Prerequisites

- Docker with Docker Compose
- An LLM API key and model only if you want to generate incident reports

### 1. Create your environment file

Shell:

```bash
cp .env.example .env
```

Edit `.env`. Database and Redpanda defaults work for local development. To enable report generation, replace the LLM placeholders with valid provider credentials and a LiteLLM model identifier, for example `openai/gpt-4o-mini`.

### 2. Start infrastructure and apply migrations

```bash
docker compose up -d postgres redpanda
docker compose --profile tools run --rm migrate
```

The migration service is a one-off container. It uses the same application image as the API but runs `alembic upgrade head` and exits.

### 3. Start the application services

```bash
docker compose up -d --build api consumer grafana
```

The services are then available at:

| Service | Address |
| --- | --- |
| API and OpenAPI UI | http://localhost:8000/docs |
| API health check | http://localhost:8000/health |
| Grafana | http://localhost:3000 (`admin` / `admin`) |
| PostgreSQL from your host | `localhost:5432` |
| Redpanda Kafka listener from your host | `localhost:19092` |

View service logs when debugging:

```bash
docker compose logs -f api consumer
```

To stop the stack while retaining database data:

```bash
docker compose down
```

## Local development

This project targets Python 3.13. Install dependencies with your preferred environment manager (the repository includes `pyproject.toml` and `uv.lock`).

Start the dependencies with Docker:

```bash
docker compose up -d postgres redpanda
```

Then, from a local Python environment:

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

In a separate terminal, run the event consumer:

```bash
uv run python -m app.events.consumer
```

In local mode the `.env` values should use `localhost` for PostgreSQL and Redpanda. In Docker Compose, the API and consumer override those connection values with the internal service names `postgres` and `redpanda`.

## Configuration

Configuration is read through Pydantic settings. Every setting uses the `VIGILIA_` prefix. The application reads `.env` in local execution; Docker Compose injects that file into the containers through `env_file`.

| Variable | Default | Required | Description |
| --- | --- | --- | --- |
| `VIGILIA_ENVIRONMENT` | `local` | No | Environment label returned by `/health`. Compose sets it to `docker` for the API and consumer. |
| `VIGILIA_DB_HOST` | `localhost` | No | PostgreSQL hostname. Use `localhost` locally; Compose uses `postgres` internally. |
| `VIGILIA_DB_PORT` | `5432` | No | PostgreSQL port. |
| `VIGILIA_DB_NAME` | `vigilia` | No | PostgreSQL database name. |
| `VIGILIA_DB_USER` | `vigilia` | No | PostgreSQL user. |
| `VIGILIA_DB_PASSWORD` | `vigilia` | No | PostgreSQL password. Use a secure value outside local development. |
| `VIGILIA_KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | No | Redpanda/Kafka bootstrap server. Compose uses `redpanda:9092` internally. |
| `VIGILIA_ALERTS_RECEIVED_TOPIC` | `alerts.received` | No | Kafka topic for persisted alert events. |
| `VIGILIA_INCIDENT_CORRELATION_WINDOW_MINUTES` | `45` | No | How long a recent open incident remains eligible for service-based grouping. |
| `VIGILIA_LLM_API_KEY` | — | For reports | API key passed to LiteLLM. Keep it out of version control. |
| `VIGILIA_LLM_MODEL` | — | For reports | LiteLLM model identifier, such as `openai/gpt-4o-mini`. |
| `VIGILIA_LLM_TIMEOUT_SECONDS` | `35` | No | Maximum LLM request duration in seconds. |

`VIGILIA_LLM_API_KEY` and `VIGILIA_LLM_MODEL` are optional for alert ingestion and incident correlation. Both are required to enable `POST /incidents/{incident_id}/report`; otherwise that endpoint returns an `llm_not_configured` error.

> Do not commit `.env`. It is intentionally ignored by Git. Commit safe defaults and documentation to `.env.example` instead.

## API

Interactive API documentation is available at `/docs` while the API is running.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health and environment label. |
| `POST` | `/webhooks/grafana` | Receives a Grafana Alerting webhook payload. |
| `GET` | `/incidents` | Lists incident summaries. |
| `GET` | `/incidents/{incident_id}` | Retrieves an incident and its associated alert timeline. |
| `POST` | `/incidents/{incident_id}/report` | Generates, validates, and stores an LLM incident report. |
| `GET` | `/incidents/{incident_id}/reports` | Lists reports previously generated for an incident. |

## Send a sample alert

The repository provides a small Grafana-webhook sender. With the API running locally, send a firing alert with:

```bash
uv run python scripts/send_grafana_alert.py --service payments-api --alert-name CpuHigh --status firing --severity warning
```

Then send its resolution using the same service and alert name (the script derives the same fingerprint):

```bash
uv run python scripts/send_grafana_alert.py --service payments-api --alert-name CpuHigh --status resolved --severity warning
```

For an incident with multiple alerts, send firing alerts for the same `--service`, then resolve each one. The incident remains open until every alert fingerprint is resolved.

## Docker networking note

The Compose services use Docker DNS to reach each other: the API and consumer connect to `postgres:5432` and `redpanda:9092`. Your browser and local tools run on the host, so they use published host ports such as `localhost:8000` and `localhost:19092`.

Redpanda listens on `0.0.0.0` inside its container so Docker can route incoming traffic. It advertises `redpanda:9092` to containers and `localhost:19092` to clients running on your computer.

## Useful commands

```bash
# Check migration state
docker compose --profile tools run --rm migrate alembic current

# Follow a single service
docker compose logs -f consumer

# Rebuild and restart the API
docker compose up -d --build api

# Run the test suite locally
uv run pytest
```
