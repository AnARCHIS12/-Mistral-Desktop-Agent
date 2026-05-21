from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Mistral Desktop Agent"
    host: str = "0.0.0.0"
    port: int = 48723

    mistral_api_key: str = Field(default="", alias="MISTRAL_API_KEY")
    mistral_model: str = Field(default="mistral-large-latest", alias="MISTRAL_MODEL")
    mistral_api_url: str = Field(
        default="https://api.mistral.ai/v1/chat/completions",
        alias="MISTRAL_API_URL",
    )

    telegram_bot_token: Optional[str] = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    enable_telegram: bool = Field(default=True, alias="ENABLE_TELEGRAM")

    database_path: Path = Field(default=Path("data/agent_memory.sqlite3"), alias="DATABASE_PATH")
    screenshot_path: Path = Field(default=Path("data/latest_screenshot.png"), alias="SCREENSHOT_PATH")
    file_access_mode: str = Field(default="full", alias="FILE_ACCESS_MODE")
    allowed_file_roots: str = Field(default="", alias="ALLOWED_FILE_ROOTS")
    terminal_workdir: Path = Field(default=Path.home(), alias="TERMINAL_WORKDIR")

    max_steps: int = Field(default=50, alias="MAX_STEPS")
    max_retries: int = Field(default=3, alias="MAX_RETRIES")
    loop_delay_seconds: float = Field(default=1.0, alias="LOOP_DELAY_SECONDS")
    max_repeated_actions: int = Field(default=3, alias="MAX_REPEATED_ACTIONS")
    terminal_timeout_seconds: int = Field(default=30, alias="TERMINAL_TIMEOUT_SECONDS")
    browser_headless: bool = Field(default=False, alias="BROWSER_HEADLESS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
