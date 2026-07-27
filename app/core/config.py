from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vigilia"
    environment: str = "local"

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "vigilia"
    db_user: str = "vigilia"
    db_password: str = "vigilia"

    kafka_bootstrap_servers: str = "localhost:9092"
    alerts_received_topic: str = "alerts.received"

    incident_correlation_window_minutes: int = 45

    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = 35.0

    grafana_webhook_hmac_secret: SecretStr | None = None

    grafana_webhook_max_age_seconds: int = Field(
        default=300,
        gt=0,
        le=3600,
    )

    api_token: SecretStr | None = None

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    model_config = SettingsConfigDict(
        env_prefix="VIGILIA_",
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
