# ADR 0002: Durable investigation jobs

An investigation is a PostgreSQL resource and Redpanda carries notifications that work is available. The API never waits for analysis.

Claims use leases and attempt tokens. Retry scheduling is stored through the existing outbox, avoiding a separate in-memory scheduler. Consumers assume at-least-once delivery and record processed event IDs transactionally.
