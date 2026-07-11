from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    llm_provider: Literal["anthropic", "ollama", "nvidia", "router"] = "ollama"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-8"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    nvidia_api_key: str | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "deepseek-ai/deepseek-v4-flash"
    nvidia_extra_body: str = ""  # JSON merged into each request, e.g. chat_template_kwargs
    # Router (LLM_PROVIDER=router): specialized NVIDIA models per task type.
    router_code_model: str = "qwen/qwen3.5-122b-a10b"
    router_research_model: str = "deepseek-ai/deepseek-v4-flash"
    router_chat_model: str = "mistralai/mistral-large-3-675b-instruct-2512"
    llm_max_tokens: int = 4096
    llm_max_tool_rounds: int = 8
    llm_timeout_seconds: float = 300.0  # hosted free tiers can cold-start slowly

    # Telegram
    telegram_bot_token: str | None = None
    telegram_allowed_chat_ids: str = ""

    # API
    sirius_api_key: str | None = None
    host: str = "0.0.0.0"
    port: int = 8000

    # Storage
    data_dir: Path = Path("data")
    database_url: str = "sqlite:///data/sirius.db"

    # Misc
    timezone: str = "Asia/Taipei"
    encryption_key: str | None = None
    history_turns: int = 20

    @property
    def chroma_dir(self) -> Path:
        return self.data_dir / "chroma"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def allowed_chat_ids(self) -> set[int]:
        """Numeric chat ids only; placeholder/invalid entries are ignored so a
        half-filled .env never crashes the bot at startup."""
        ids = set()
        for part in self.telegram_allowed_chat_ids.split(","):
            part = part.strip()
            if part.lstrip("-").isdigit():
                ids.add(int(part))
        return ids

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.chroma_dir, self.backup_dir, self.log_dir):
            path.mkdir(parents=True, exist_ok=True)


def validate_settings(settings: Settings) -> None:
    """Fail fast at startup when mandatory configuration is missing.

    Raises SystemExit with a human-readable list of problems so a
    misconfigured container dies immediately instead of failing later.
    """
    problems: list[str] = []
    if settings.llm_provider in ("nvidia", "router") and not settings.nvidia_api_key:
        problems.append("NVIDIA_API_KEY is required when LLM_PROVIDER is 'nvidia' or 'router'.")
    if settings.llm_provider == "anthropic" and not settings.anthropic_api_key:
        problems.append("ANTHROPIC_API_KEY is required when LLM_PROVIDER is 'anthropic'.")
    if settings.nvidia_extra_body:
        import json

        try:
            json.loads(settings.nvidia_extra_body)
        except ValueError:
            problems.append("NVIDIA_EXTRA_BODY is not valid JSON.")
    if problems:
        raise SystemExit(
            "Configuration errors (fix your .env / environment variables):\n- "
            + "\n- ".join(problems)
        )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
