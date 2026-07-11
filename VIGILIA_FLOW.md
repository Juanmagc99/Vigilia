# Vigilia: Current Flow And Incident Plan

## Project Vision

Vigilia is a FastAPI backend that receives alerts from Grafana Alerting, normalizes them, stores them in PostgreSQL, and publishes events to Redpanda/Kafka so background workers can react to them.

The goal is not to replace Grafana. Grafana remains responsible for detecting alert conditions and sending webhooks. Vigilia adds an operational layer on top of Grafana so we can answer questions such as:

- which alert arrived
- how it was normalized
- how it was persisted
- which event was emitted
- how related alerts are grouped into incidents
- how incident reports will be generated later

The product direction is:

```text
Alert = atomic event received from Grafana
Incident = group of related alerts
Report = future summary/enrichment of an incident
```

The current sprint is focused on closing the `alerts -> incidents` loop before adding AI, reports, or more advanced workflows.

## Current Alert Flow

The alert ingestion flow is implemented:

```text
Grafana Alerting
  -> HTTP webhook
  -> FastAPI
  -> GrafanaWebhookPayload
  -> NormalizedAlert
  -> Alert in PostgreSQL
  -> AlertReceivedMessage
  -> Redpanda/Kafka topic alerts.received
  -> event consumer
  -> incident correlation service
  -> Incident in PostgreSQL
```

Important files:

```text
app/schemas/grafana.py
  Input models for the Grafana webhook payload.

app/schemas/alerts.py
  Internal NormalizedAlert model.

app/services/grafana_normalizer.py
  Converts Grafana payloads into normalized alerts.

app/db/models/alert.py
  Persistent Alert model.

app/repositories/alert_repository.py
  Converts normalized alerts into Alert rows and stages persistence.

app/services/alert_ingestion_service.py
  Orchestrates normalization, persistence, and event publishing.

app/events/message.py
  Defines AlertReceivedMessage.

app/events/publisher.py
  Publishes alert events to Redpanda/Kafka.

app/events/consumer.py
  Consumes alerts.received, loads the persisted Alert, and calls the incident correlator.
```

## Kafka, Redpanda, Publishers, And Consumers

Redpanda is used as a Kafka-compatible broker. In Vigilia, it is the event log between the API process and background processing.

Current configuration:

```text
bootstrap servers: localhost:9092
main topic: alerts.received
```

Mental model:

```text
Publisher / Producer
  writes messages to a topic

Topic
  durable event log/channel

Consumer
  reads messages from a topic

Worker
  background process running a consumer
```

In Vigilia:

```text
FastAPI publishes AlertReceivedMessage events
Redpanda stores those events in alerts.received
app.events.consumer reads them
the consumer calls incident_correlation_service.correlate_alert()
```

The consumer is intentionally a thin adapter. It should connect Kafka to the application service, not contain the incident business rules itself.

Current consumer behavior:

```text
1. Poll alerts.received.
2. Decode the Kafka message value as UTF-8 JSON.
3. Validate it as AlertReceivedMessage.
4. Open a database Session.
5. Load Alert by alert_id.
6. Call correlate_alert(session, alert).
7. Log the resulting incident status.
```

## Core Concepts

### Alert

An `Alert` is one concrete event received and stored in the database.

Example:

```text
Alert #1
status=firing
fingerprint=a1b2
service=server-01.local
received_at=12:00
```

If Grafana later sends the resolved event, it is stored as another row:

```text
Alert #2
status=resolved
fingerprint=a1b2
service=server-01.local
received_at=12:10
```

Those two rows are separate events, even though they belong to the same alert instance.

### Fingerprint

In Grafana, the fingerprint is a stable identity for a concrete alert instance.

For Vigilia:

```text
fingerprint = stable identity of one alert instance
```

It lets Vigilia match the lifecycle of one alert:

```text
HostDown server-01.local firing   fingerprint=a1b2
HostDown server-01.local resolved fingerprint=a1b2
```

The fingerprint is useful for pairing `firing` and `resolved` events from the same alert instance, but it is not the same thing as an incident.

```text
fingerprint identifies one alert instance
incident groups multiple related alert instances
```

### Service

`service` is Vigilia's first grouping key for incidents.

It currently comes from normalization:

```text
labels["service"] or labels["instance"] or "unknown"
```

For a `firing` alert, Vigilia uses `service` to decide whether the alert belongs to a recent open incident.

### Incident

An `Incident` represents an operational problem grouped from related alerts.

Example:

```text
Incident #1
service=server-01.local
status=open
severity=critical
```

It can contain multiple alert instances:

```text
HostDown fingerprint=a1b2
HighCPU  fingerprint=c3d4
DiskFull fingerprint=e5f6
```

Even if each alert has a different fingerprint, they can belong to the same incident if they affect the same service and arrive close enough in time.

### IncidentAlert

`IncidentAlert` is the join table between incidents and alerts.

Conceptual model:

```text
incidents
  id = inc-1

incident_alerts
  incident_id = inc-1
  alert_id = alert-1
  incident_id = inc-1
  alert_id = alert-2

alerts
  alert-1 fingerprint=a1b2 status=firing
  alert-2 fingerprint=c3d4 status=firing
```

This table allows Vigilia to reconstruct an incident timeline from the concrete alert events that created or changed it.

## Incident Correlation Rule V1

The first correlation version is intentionally deterministic and easy to explain.

### When A Firing Alert Arrives

Rule:

```text
Find a recent open incident with the same service.

If one exists:
  attach the alert to that incident.

If none exists:
  create a new incident.

Update incident activity:
  updated_at = alert.received_at
  severity = highest current/incoming severity
```

The correlation window prevents a long-running open incident from absorbing unrelated alerts forever.

Current setting:

```text
incident_correlation_window_minutes
```

Environment variable:

```text
VIGILIA_INCIDENT_CORRELATION_WINDOW_MINUTES
```

### When A Resolved Alert Arrives

Rule:

```text
Find an open incident that already contains an alert with the same fingerprint.

If one exists:
  attach the resolved event to that incident.
  recalculate the latest status per fingerprint.

If none exists:
  log that the resolved alert has no open incident.
```

`resolved` is matched by fingerprint because it belongs to one concrete alert instance that was previously firing.

### When An Incident Is Resolved

An incident is not resolved just because one `resolved` alert arrives.

It is resolved only when all fingerprints associated with that incident have latest status `resolved`.

Example:

```text
Incident #1
  cpu-api    firing
  memory-api firing
  cpu-api    resolved
```

Latest status by fingerprint:

```text
cpu-api    = resolved
memory-api = firing
```

The incident stays open.

Then:

```text
memory-api resolved
```

Latest status:

```text
cpu-api    = resolved
memory-api = resolved
```

Result:

```text
Incident #1 -> resolved
```

## Severity Rule

Incident severity should keep the highest severity seen so far, instead of blindly taking the latest alert severity.

Current ranking:

```text
critical > warning > info > unknown
```

Example:

```text
Incident severity = critical
Incoming alert severity = warning
Result = critical
```

The current implementation keeps this helper local to `incident_repository.py` to avoid importing a service from a repository. This is acceptable for now because the function is small and used exactly where the incident model is updated.

Future improvement:

```text
Normalize Grafana severity values at ingestion time.
Examples:
  warn -> warning
  missing -> unknown
  unsupported value -> unknown
```

## Layer Responsibilities

### Models

Models define what exists in the database.

```text
Alert
Incident
IncidentAlert
```

### Repositories

Repositories know how to read and write database state. They prepare changes but do not commit transactions.

Examples:

```text
find_recent_open_incident_for_service
find_open_incident_by_fingerprint
create_incident_from_alert
attach_alert_to_incident
update_incident_activity
get_latest_alert_statuses_for_incident
resolve_incident
```

### Services

Services apply use cases and business rules. They own commit/rollback for the unit of work.

Main incident service:

```text
app/services/incident_correlation_service.py
```

Main function:

```text
correlate_alert(session, alert)
```

It decides:

```text
if alert.status == firing:
  find/create incident and attach alert

if alert.status == resolved:
  find incident by fingerprint
  attach resolved alert
  close incident if no active fingerprints remain
```

### Events

Events connect Kafka/Redpanda with application logic.

The consumer converts:

```text
AlertReceivedMessage
```

into:

```text
Alert loaded from PostgreSQL
```

and then calls:

```text
correlate_alert(session, alert)
```

## Transaction Rule

Repositories do not call `commit()` or `rollback()`.

Services own transaction boundaries:

```text
repositories:
  session.add(...)
  session.add_all(...)
  return objects

services:
  commit
  refresh
  rollback on failure
```

Reason:

```text
One use case can involve multiple repository operations.
Those operations should succeed or fail together.
```

This currently applies to:

```text
alert_repository.py + alert_ingestion_service.py
incident_repository.py + incident_correlation_service.py
```

## Current Manual Test Script

A synthetic Grafana webhook sender exists:

```text
scripts/send_grafana_alert.py
```

Basic usage:

```powershell
uv run python scripts\send_grafana_alert.py --service payments-api --status firing --severity critical
```

Useful arguments:

```text
--service
--status firing|resolved
--severity
--alert-name
--instance
--fingerprint
--webhook-url
```

If `--fingerprint` is omitted, the script generates a deterministic fingerprint from:

```text
service + alert-name + instance
```

This means these two commands target the same alert instance:

```powershell
uv run python scripts\send_grafana_alert.py --service payments-api --alert-name CpuHigh --status firing --severity warning
uv run python scripts\send_grafana_alert.py --service payments-api --alert-name CpuHigh --status resolved --severity warning
```

Example multi-alert incident test:

```powershell
uv run python scripts\send_grafana_alert.py --service payments-api --alert-name CpuHigh --status firing --severity warning
uv run python scripts\send_grafana_alert.py --service payments-api --alert-name MemoryHigh --status firing --severity critical
uv run python scripts\send_grafana_alert.py --service payments-api --alert-name CpuHigh --status resolved --severity warning
uv run python scripts\send_grafana_alert.py --service payments-api --alert-name MemoryHigh --status resolved --severity critical
```

Expected result:

```text
CpuHigh firing       -> creates Incident open
MemoryHigh firing    -> attaches to same Incident by service
CpuHigh resolved     -> Incident stays open
MemoryHigh resolved  -> Incident becomes resolved
```

## Useful Commands

Infrastructure:

```powershell
docker compose up -d postgres redpanda grafana
```

Migrations:

```powershell
uv run alembic upgrade head
uv run alembic current
```

API:

```powershell
uv run uvicorn app.main:app --reload
```

Consumer:

```powershell
uv run python -m app.events.consumer
```

Quick import check:

```powershell
uv run python -c "from app.services.incident_correlation_service import correlate_alert; print('ok')"
```

## End-To-End Test Checklist

Before moving to the next sprint, verify:

```text
firing creates a new open incident
second firing with same service attaches to the same incident
resolved attaches by fingerprint
incident stays open while any fingerprint is still firing
incident becomes resolved when all fingerprints are resolved
severity does not downgrade accidentally
```

This has been manually tested successfully with Grafana and with the synthetic script.

## What Is Done

Implemented:

```text
Grafana webhook ingestion
Grafana payload normalization
Alert persistence in PostgreSQL
AlertReceivedMessage publishing to Redpanda/Kafka
alerts.received consumer
Incident and IncidentAlert models
Alembic migration for incidents and incident_alerts
Incident repository
Incident correlation service
Consumer connected to the correlator
Incident severity high-watermark behavior
Synthetic alert sending script
Manual end-to-end validation
```

## Current Focus

The current phase is still:

```text
Close alerts -> incidents properly.
```

The reason is deliberate: before building AI/reporting/product endpoints, Vigilia needs a reliable operational core:

```text
receive alert
persist Alert
publish event
consume event
create/update/resolve Incident
```

## Next Steps

Recommended next steps before automated tests:

1. Harden consumer offset handling.

Current consumer likely relies on Kafka auto-commit behavior. A stronger version should:

```text
enable.auto.commit = False
process message successfully
commit Kafka offset manually
do not commit offset if processing fails
```

Reason:

```text
If incident correlation fails, the event should not be marked as processed.
```

2. Review idempotency around incident correlation.

Cases to reason about:

```text
Kafka redelivers the same alert event
same firing event is processed twice
same resolved event is processed twice
```

Current protections:

```text
alerts has a unique constraint for idempotency
incident_alerts has a composite primary key
attach_alert_to_incident skips existing links
```

Still worth validating behavior end-to-end.

3. Normalize severity at ingestion.

Reason:

```text
Grafana severity is an external free-form label.
Vigilia should use stable internal severity values.
```

4. Add read endpoints for incidents.

Initial API:

```text
GET /incidents
GET /incidents/{incident_id}
```

Incident detail should eventually include associated alerts ordered by `received_at`.

5. Add automated tests at the end of this phase.

Suggested tests:

```text
highest severity keeps critical over warning
firing creates incident
second firing with same service attaches to same incident
resolved is matched by fingerprint
incident remains open while another fingerprint is firing
incident resolves when all fingerprints are resolved
consumer handler processes a valid AlertReceivedMessage
```

## Decisions Taken

- Do not call AI for each individual alert.
- Use AI later on incidents and reports, not on raw alert events.
- Use fingerprint to pair events from the same alert instance.
- Use service/instance plus a time window to group alerts into incidents.
- Resolve incidents only when all associated fingerprints have latest status `resolved`.
- Keep the first correlation version simple, deterministic, and explainable.
- Keep repositories free of transaction ownership.
- Keep services responsible for commit/rollback.
- Keep the consumer as a thin adapter.
- Avoid importing services from repositories.
- Keep tests for the end of this stabilization phase.
