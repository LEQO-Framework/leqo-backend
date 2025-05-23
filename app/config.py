"""
Load environment variables from the .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_protocol: str = "http"
    api_domain: str = "localhost"
    api_port: int = 8000

    cors_allow_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
