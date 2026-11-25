from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    DEMO_RESTAURANT_URL: str = "http://demo-restaurant:8001"
    SMTP_HOST: str = "mailpit"
    SMTP_PORT: int = 1025
    SMTP_SENDER: str = "noreply@avito-kitchen.local"
    SMTP_TIMEOUT_SECONDS: float = 10.0
    SMTP_USE_TLS: bool = False
    SMTP_START_TLS: bool = False
    SMTP_VALIDATE_CERTS: bool = True
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    EMAIL_VERIFICATION_BASE_URL: str = "http://127.0.0.1:8000/docs"
    AUTH_REGISTER_RATE_LIMIT: int = 10
    AUTH_RESEND_RATE_LIMIT: int = 10
    AUTH_VERIFY_RATE_LIMIT: int = 20
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
