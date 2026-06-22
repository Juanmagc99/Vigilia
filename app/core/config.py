from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vigilia"
    environment: str = "local"

    model_config = SettingsConfigDict(env_prefix="VIGILIA_")


settings = Settings()
