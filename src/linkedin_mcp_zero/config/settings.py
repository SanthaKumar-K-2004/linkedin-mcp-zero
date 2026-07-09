from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from linkedin_mcp_zero.config.defaults import CACHE_TTL_SECONDS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LINKEDIN_MCP_",
        env_file=(".env",),
        extra="ignore",
        populate_by_name=True,
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
    allowed_resume_dirs: list[str] | None = None
    cdp_url: str = "http://127.0.0.1:9222"
    browser_idle_seconds: int = 300
    enable_browser: bool = False
    enable_patchright_fallback: bool = False
    browser_user_data_dir: str | None = None
    exact_token_count: bool = False
    token_count_model: str = "claude-sonnet-4-5"
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    li_at: str | None = Field(default=None, validation_alias="LI_AT")
    api_key: str | None = Field(default=None, validation_alias="API_KEY")
    cors_allowed_origins: list[str] = Field(default=["*"], validation_alias="CORS_ALLOWED_ORIGINS")
    rate_limit_per_minute: int = Field(default=60, validation_alias="RATE_LIMIT_PER_MINUTE")
    oauth_metadata_url: str | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    oauth_server_url: str | None = None
