from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    kitchen_api_url: str = "http://localhost:8000"

    restaurant_external_id: str = Field(min_length=1)
    restaurant_name: str = Field(min_length=1)
    restaurant_description: str  | None = None

    menu_external_id: str = Field(min_length=1)
    menu_name: str = Field(min_length=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
