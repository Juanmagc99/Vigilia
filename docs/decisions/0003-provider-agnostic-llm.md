# ADR 0003: Provider-agnostic model adapter through LiteLLM

## Context

Vigilia needs structured incident analysis without making application services,
domain objects, workers, or persisted investigations depend on a specific model
vendor. The previous implementation contained an LLM client, but report generation
also owned prompt rendering, database access, concurrency and persistence. That made
the provider boundary difficult to replace and the execution non-durable.

## Decision

The application declares the `IncidentAnalyzer` port. The production implementation
is `LiteLLMIncidentAnalyzer`, an outbound adapter using the LiteLLM Python SDK. The
configured model is a LiteLLM model identifier; provider credentials and optional
base URL are configuration, not domain concepts.

The adapter requests a strict JSON Schema response and maps it into Vigilia domain
objects. Structured shape validation is followed by evidence validation: a model may
only cite evidence identifiers that were present in its input. Provider exceptions
are translated into transient or permanent application errors. LiteLLM retries are
disabled because the durable worker owns retry policy.

`SimulatedIncidentAnalyzer` remains available as another implementation of the same
port. It is the default for local development and infrastructure exercises.

## Consequences

- Application and domain code contain no provider SDK types or provider names.
- Changing provider or model is configuration, but changing the prompt/output
  contract changes `analyzer_version` so results remain reproducible.
- Only models supporting JSON Schema structured output are valid for this adapter.
- The worker, not LiteLLM, decides whether and when a failed attempt is retried.
- Provider and model are stored for every attempt; token usage, estimated cost,
  response ID and latency are added when a response succeeds. Prompts and full raw
  responses are not persisted.
- LiteLLM's cost value is operational metadata and may be unavailable; provider
  billing remains authoritative.
- RAG will remain a separate application concern. Retrieved chunks will enter
  `InvestigationContext`; the model adapter will not own document indexing or search.
