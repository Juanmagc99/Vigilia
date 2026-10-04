from functools import cached_property
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vigilia"
    environment: str = "local"

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "vigilia"
    db_user: str = "vigilia"
    db_password: SecretStr = SecretStr("vigilia")

    kafka_bootstrap_servers: str = "localhost:19092"
    alerts_received_topic: str = "alerts.received.v1"
    legacy_alerts_received_topic: str = "alerts.received"
    investigations_requested_topic: str = "investigations.requested.v1"
    kafka_flush_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    outbox_batch_size: int = Field(default=100, ge=1, le=1000)
    outbox_poll_interval_seconds: float = Field(default=1.0, gt=0, le=60)
    outbox_lock_seconds: int = Field(default=60, ge=1, le=3600)
    outbox_max_retry_delay_seconds: int = Field(default=300, ge=1, le=86400)

    incident_correlation_window_minutes: int = Field(default=45, ge=1)
    investigation_max_attempts: int = Field(default=3, ge=1, le=20)
    investigation_retry_max_delay_seconds: int = Field(default=60, ge=1, le=3600)
    investigation_lease_seconds: int = Field(default=120, ge=5, le=86400)
    worker_poll_timeout_seconds: float = Field(default=1.0, gt=0, le=30)

    investigation_analyzer: Literal["simulated", "litellm"] = "simulated"
    llm_model: str | None = None
    llm_api_key: SecretStr | None = None
    llm_api_base: str | None = None
    llm_timeout_seconds: float = Field(default=45.0, gt=0, le=300)
    llm_max_output_tokens: int = Field(default=1200, ge=100, le=16000)
    llm_max_alerts: int = Field(default=50, ge=1, le=500)

    rag_enabled: bool = False
    rag_embedding_model: str | None = None
    rag_embedding_api_key: SecretStr | None = None
    rag_embedding_api_base: str | None = None
    rag_embedding_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    rag_embedding_batch_size: int = Field(default=64, ge=1, le=256)
    rag_chunk_size: int = Field(default=2400, ge=200, le=12000)
    rag_chunk_overlap: int = Field(default=300, ge=0, le=2000)
    rag_max_document_characters: int = Field(default=250000, ge=1000, le=2000000)
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_max_context_characters: int = Field(default=16000, ge=1000, le=100000)

    grafana_webhook_hmac_secret: SecretStr | None = None
    grafana_webhook_max_age_seconds: int = Field(default=300, gt=0, le=3600)
    api_token: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_prefix="VIGILIA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_analyzer_configuration(self) -> "Settings":
        if self.investigation_analyzer == "litellm" and not self.llm_model:
            raise ValueError("VIGILIA_LLM_MODEL is required for the LiteLLM analyzer")
        if self.rag_enabled and not self.rag_embedding_model:
            raise ValueError(
                "VIGILIA_RAG_EMBEDDING_MODEL is required when RAG is enabled"
            )
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError(
                "VIGILIA_RAG_CHUNK_OVERLAP must be smaller than chunk size"
            )
        return self

    @cached_property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{quote_plus(self.db_user)}:"
            f"{quote_plus(self.db_password.get_secret_value())}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def analyzer_version(self) -> str:
        if self.investigation_analyzer == "simulated":
            base_version = "simulated-v1"
        else:
            base_version = f"litellm:{self.llm_model}:investigation-v1"
        if self.rag_enabled:
            return f"{base_version}:rag:{self.rag_embedding_model}:v1"
        return base_version
