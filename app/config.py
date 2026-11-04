"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Stock Financials API"
    APP_VERSION: str = "1.0.0"
    CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
