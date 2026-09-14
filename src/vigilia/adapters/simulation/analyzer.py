from decimal import Decimal

from vigilia.domain.models import (
    AnalysisOutput,
    AnalysisResult,
    AnalysisUsage,
    InvestigationContext,
)


class SimulatedIncidentAnalyzer:
    version = "simulated-v1"
    provider = "simulation"
    model = version

    async def analyze(self, context: InvestigationContext) -> AnalysisOutput:
        incident = context.incident
        evidence = tuple(
            {
                "kind": "alert",
                "id": f"alert:{alert.id}",
                "summary": alert.summary or alert.alert_name or alert.fingerprint,
            }
            for alert in incident.alerts
        )
        if not evidence:
            result = AnalysisResult(
                schema="incident_investigation.v1",
                outcome="insufficient_evidence",
                summary=f"Incident {incident.id} has no alert evidence to analyze.",
                hypotheses=(),
                evidence=(),
                recommended_checks=("Attach alert evidence before investigating.",),
                missing_information=("Alert timeline",),
            )
        else:
            result = AnalysisResult(
                schema="incident_investigation.v1",
                outcome="analysis",
                summary=(
                    f"{incident.title} affects {incident.service} with "
                    f"{len(evidence)} alert evidence item(s)."
                ),
                hypotheses=(
                    {
                        "statement": "No probable cause is inferred by the simulated analyzer.",
                        "evidence_ids": [item["id"] for item in evidence],
                    },
                ),
                evidence=evidence,
                recommended_checks=(
                    (
                        f"Inspect telemetry for {incident.service} around "
                        f"{incident.started_at.isoformat()}."
                    ),
                ),
                missing_information=("Operational knowledge is not connected yet.",),
            )
        return AnalysisOutput(
            result=result,
            usage=AnalysisUsage(
                provider="simulation",
                model=self.version,
                response_id=None,
                prompt_tokens=0,
                cached_prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                estimated_cost_usd=Decimal(0),
                latency_ms=0,
            ),
        )
