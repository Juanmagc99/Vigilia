from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HypothesisSchema(BaseModel):
    statement: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1, max_length=50)
    model_config = ConfigDict(extra="forbid")


class InvestigationDraftSchema(BaseModel):
    outcome: Literal["analysis", "insufficient_evidence"]
    summary: str = Field(min_length=1, max_length=4000)
    hypotheses: list[HypothesisSchema] = Field(max_length=10)
    recommended_checks: list[str] = Field(max_length=20)
    missing_information: list[str] = Field(max_length=20)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_outcome(self) -> "InvestigationDraftSchema":
        if self.outcome == "analysis" and not self.hypotheses:
            raise ValueError("analysis outcome requires at least one hypothesis")
        if self.outcome == "insufficient_evidence" and self.hypotheses:
            raise ValueError("insufficient_evidence cannot contain hypotheses")
        return self
