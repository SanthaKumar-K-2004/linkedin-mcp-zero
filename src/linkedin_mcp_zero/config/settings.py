from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from linkedin_mcp_zero.config.defaults import CACHE_TTL_SECONDS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LINKEDIN_MCP_",
        env_file=(".env",),
        extra="ignore",
    )

    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    timeout_seconds: float = 15
    cache_ttl_seconds: int = CACHE_TTL_SECONDS
    enable_voyager: bool = False
    http_proxy: str | None = Field(default=None, validation_alias="HTTP_PROXY")
    https_proxy: str | None = Field(default=None, validation_alias="HTTPS_PROXY")
    data_dir: str | None = None
    cdp_url: str = "http://127.0.0.1:9222"
    browser_idle_seconds: int = 300
    enable_patchright_fallback: bool = False
    browser_user_data_dir: str | None = None
    li_at: str | None = Field(default=None, validation_alias="LI_AT")
