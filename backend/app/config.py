from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./partner_agent.db"
    armoriq_mode: str = "local"
    armoriq_base_url: str | None = None
    armoriq_api_key: str | None = None
    armoriq_fail_closed: bool = True
    armoriq_user_id: str = "partner-agent-service"
    armoriq_agent_id: str = "armoriq-partner-agent"
    armoriq_operator_email: str | None = None
    armoriq_local_tool_namespace: str = "partner-agent-local"
    mcp_server_api_key: str | None = None
    armoriq_signing_key: str = "local-development-key-change-me"
    permit_ttl_seconds: int = 120
    max_actions_per_run: int = 100
    max_outreach_per_mission: int = 10
    autonomous_execution_enabled: bool = True
    background_worker_interval_seconds: int = 3600
    background_worker_run_once: bool = False
    model_mode: str = "deterministic"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-sol"
    openai_timeout_seconds: float = 45.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
