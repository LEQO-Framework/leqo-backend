"""
Load environment variables from the .env file.
"""

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration settings for the backend, loaded from a `.env` file.

    :param api_base_url (AnyHttpUrl): Base URL of the backend API, used for generating absolute URLs.
    :param cors_allow_origins (list[str]): List of allowed origins for CORS. Wildcard `*` allows all origins.
    :param cors_allow_credentials (bool): Whether CORS requests can include credentials (e.g., cookies or headers).
    :param cors_allow_methods (list[str]): List of HTTP methods allowed for CORS. Wildcard `*` allows all methods.
    :param cors_allow_headers (list[str]): List of HTTP headers allowed in CORS requests. Wildcard `*` allows all headers.
    """

    api_base_url: AnyHttpUrl = AnyHttpUrl(url="http://localhost:8000/")

    cors_allow_origins: list[str] = ["*"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
