from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    DEMO_RESTAURANT_URL: str = "http://demo-restaurant:8001"
    SMTP_HOST: str = "mailpit"
    SMTP_PORT: int = Field(default=1025, gt=0, le=65535)
    SMTP_SENDER: str = "noreply@avito-kitchen.local"
    SMTP_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0)
    SMTP_USE_TLS: bool = False
    SMTP_START_TLS: bool = False
    SMTP_VALIDATE_CERTS: bool = True
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAIL_VERIFICATION_BASE_URL: str = "http://127.0.0.1:8000/docs"
    AUTH_REGISTER_RATE_LIMIT: int = Field(default=10, gt=0)
    AUTH_RESEND_RATE_LIMIT: int = Field(default=10, gt=0)
    AUTH_VERIFY_RATE_LIMIT: int = Field(default=20, gt=0)
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, gt=0)
    AUTH_RATE_LIMIT_MAX_BUCKETS: int = Field(default=10_000, gt=0)
    AUTH_RATE_LIMIT_CLEANUP_INTERVAL_SECONDS: int = Field(default=60, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
