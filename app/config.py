"""
Load environment variables from the .env file.
"""

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    api_base_url: AnyHttpUrl = AnyHttpUrl(url="http://localhost:8000/")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
