from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Any

import litellm
from pydantic import ValidationError

from vigilia.adapters.llm.prompt import build_messages
from vigilia.adapters.llm.schemas import InvestigationDraftSchema
from vigilia.application.errors import (
    PermanentInvestigationError,
    TransientInvestigationError,
)
from vigilia.domain.models import (
    AnalysisOutput,
    AnalysisResult,
    AnalysisUsage,
    InvestigationContext,
)

TRANSIENT_PROVIDER_ERRORS = (
    litellm.Timeout,
    litellm.RateLimitError,
    litellm.APIConnectionError,
    litellm.ServiceUnavailableError,
    litellm.APIError,
)

PERMANENT_PROVIDER_ERRORS = (
    litellm.AuthenticationError,
    litellm.PermissionDeniedError,
    litellm.BadRequestError,
    litellm.NotFoundError,
    litellm.ContextWindowExceededError,
    litellm.ContentPolicyViolationError,
    litellm.UnsupportedParamsError,
)


class LiteLLMIncidentAnalyzer:
    schema_version = "incident_investigation.v1"

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        api_base: str | None,
        timeout_seconds: float,
        max_output_tokens: int,
        max_alerts: int,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._api_base = api_base
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens
        self._max_alerts = max_alerts
        self.version = f"litellm:{model}:investigation-v1"
        self.provider = "litellm"
        self.model = model

    async def analyze(self, context: InvestigationContext) -> AnalysisOutput:
        started_at = perf_counter()
        request: dict[str, Any] = {
            "model": self._model,
            "messages": build_messages(context, max_alerts=self._max_alerts),
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "incident_investigation",
                    "schema": InvestigationDraftSchema.model_json_schema(),
                    "strict": True,
                },
            },
            "timeout": self._timeout_seconds,
            "max_tokens": self._max_output_tokens,
            "num_retries": 0,
        }
        if self._api_key:
            request["api_key"] = self._api_key
        if self._api_base:
            request["api_base"] = self._api_base

        try:
            response = await litellm.acompletion(**request)
        except PERMANENT_PROVIDER_ERRORS as exc:
            raise PermanentInvestigationError(
                message="The configured model rejected the investigation request",
                code="analyzer_request_rejected",
                metadata={"model": self._model, "provider_error": type(exc).__name__},
            ) from exc
        except TRANSIENT_PROVIDER_ERRORS as exc:
            raise TransientInvestigationError(
                message="The configured model provider is temporarily unavailable",
                code="analyzer_provider_unavailable",
                metadata={"model": self._model, "provider_error": type(exc).__name__},
            ) from exc

        content = self._response_content(response)
        try:
            draft = InvestigationDraftSchema.model_validate_json(content)
        except ValidationError as exc:
            raise PermanentInvestigationError(
                message="The configured model returned an invalid investigation",
                code="analyzer_invalid_response",
                metadata={"model": self._model},
            ) from exc

        result = self._to_result(draft, context)
        return AnalysisOutput(
            result=result,
            usage=self._usage(response, int((perf_counter() - started_at) * 1000)),
        )

    def _response_content(self, response: Any) -> str:
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            raise PermanentInvestigationError(
                message="The configured model returned an unreadable response",
                code="analyzer_invalid_response",
                metadata={"model": self._model},
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise PermanentInvestigationError(
                message="The configured model returned an empty response",
                code="analyzer_empty_response",
                metadata={"model": self._model},
            )
        return content

    def _to_result(
        self, draft: InvestigationDraftSchema, context: InvestigationContext
    ) -> AnalysisResult:
        available = {
            f"alert:{alert.id}": {
                "kind": "alert",
                "id": f"alert:{alert.id}",
                "summary": alert.summary or alert.alert_name or alert.fingerprint,
            }
            for alert in context.incident.alerts[-self._max_alerts :]
        }
        available.update(
            {
                f"knowledge:{item.id}": {
                    "kind": "knowledge",
                    "id": f"knowledge:{item.id}",
                    "document_id": str(item.document_id),
                    "title": item.title,
                    "source": item.source,
                    "service": item.service,
                    "version": item.version,
                    "similarity": item.similarity,
                }
                for item in context.knowledge
            }
        )
        cited_ids: list[str] = []
        hypotheses = []
        for hypothesis in draft.hypotheses:
            unknown = set(hypothesis.evidence_ids) - available.keys()
            if unknown:
                raise PermanentInvestigationError(
                    message="The configured model cited evidence outside its context",
                    code="analyzer_invalid_evidence_reference",
                    metadata={
                        "model": self._model,
                        "unknown_evidence_count": len(unknown),
                    },
                )
            cited_ids.extend(hypothesis.evidence_ids)
            hypotheses.append(
                {
                    "statement": hypothesis.statement,
                    "evidence_ids": list(dict.fromkeys(hypothesis.evidence_ids)),
                }
            )
        unique_cited_ids = list(dict.fromkeys(cited_ids))
        return AnalysisResult(
            schema=self.schema_version,
            outcome=draft.outcome,
            summary=draft.summary,
            hypotheses=tuple(hypotheses),
            evidence=tuple(available[item] for item in unique_cited_ids),
            recommended_checks=tuple(draft.recommended_checks),
            missing_information=tuple(draft.missing_information),
            retrieved_knowledge=tuple(
                {
                    "evidence_id": f"knowledge:{item.id}",
                    "document_id": str(item.document_id),
                    "service": item.service,
                    "title": item.title,
                    "source": item.source,
                    "version": item.version,
                    "similarity": item.similarity,
                    "content": item.content,
                }
                for item in context.knowledge
            ),
        )

    def _usage(self, response: Any, latency_ms: int) -> AnalysisUsage:
        usage = getattr(response, "usage", None)
        hidden = getattr(response, "_hidden_params", {}) or {}
        provider = hidden.get("custom_llm_provider")
        if not provider:
            provider = (
                self._model.partition("/")[0] if "/" in self._model else "unknown"
            )
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)
        prompt_details = getattr(usage, "prompt_tokens_details", None)
        cached_prompt_tokens = (
            prompt_details.get("cached_tokens")
            if isinstance(prompt_details, dict)
            else getattr(prompt_details, "cached_tokens", None)
        )
        raw_cost = hidden.get("response_cost")
        try:
            estimated_cost = Decimal(str(raw_cost)) if raw_cost is not None else None
        except InvalidOperation:
            estimated_cost = None
        return AnalysisUsage(
            provider=str(provider),
            model=str(getattr(response, "model", None) or self._model),
            response_id=getattr(response, "id", None),
            prompt_tokens=prompt_tokens,
            cached_prompt_tokens=cached_prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
            latency_ms=latency_ms,
        )
