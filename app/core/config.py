from pydantic import computed_field
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

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    model_config = SettingsConfigDict(env_prefix="VIGILIA_")


settings = Settings()
