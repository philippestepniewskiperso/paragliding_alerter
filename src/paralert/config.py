from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    db_path: str = "/data/paralert.db"
    host: str = "0.0.0.0"
    port: int = 8080

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


_instance: AppConfig | None = None


def get_app_config() -> AppConfig:
    global _instance
    if _instance is None:
        _instance = AppConfig()
    return _instance
