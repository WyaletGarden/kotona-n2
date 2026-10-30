from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://kotoba:kotoba@localhost:5432/kotoba"
    app_origin: str = "http://localhost:8000"
    cookie_secure: bool = False
    session_days: int = Field(default=14, ge=1, le=365)
    auth_limit: int = Field(default=20, ge=1, le=1000)


@lru_cache
def settings() -> Settings:
    return Settings()
