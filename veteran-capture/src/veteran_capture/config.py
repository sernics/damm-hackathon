"""Application settings loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from veteran_capture import paths


class Settings(BaseSettings):
    """Strongly-typed settings sourced from env vars and `.env`."""

    model_config = SettingsConfigDict(
        env_file=str(paths.PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API credentials
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-sonnet-4-6", validation_alias="ANTHROPIC_MODEL"
    )
    anthropic_model_moderation: str = Field(
        default="claude-haiku-4-5-20251001",
        validation_alias="ANTHROPIC_MODEL_MODERATION",
    )

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_whisper_model: str = Field(
        default="whisper-1", validation_alias="OPENAI_WHISPER_MODEL"
    )
    openai_whisper_mode: str = Field(
        default="cloud", validation_alias="OPENAI_WHISPER_MODE"
    )

    # Server
    server_host: str = Field(default="0.0.0.0", validation_alias="SERVER_HOST")
    server_port: int = Field(default=8001, validation_alias="SERVER_PORT")

    # Paths
    data_dir: Path = Field(default=paths.DEFAULT_DATA_DIR, validation_alias="DATA_DIR")
    raw_csv_dir: Path = Field(
        default=paths.DEFAULT_RAW_CSV_DIR, validation_alias="RAW_CSV_DIR"
    )
    geocoded_csv_path: Path = Field(
        default=paths.DEFAULT_GEOCODED_CSV, validation_alias="GEOCODED_CSV_PATH"
    )
    veteran_notes_dir: Path = Field(
        default=paths.DEFAULT_VETERAN_NOTES_DIR,
        validation_alias="VETERAN_NOTES_DIR",
    )

    # Logging
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_json: bool = Field(default=False, validation_alias="LOG_JSON")

    @property
    def profiles_dir(self) -> Path:
        return self.data_dir / "profiles"

    @property
    def queues_dir(self) -> Path:
        return self.data_dir / "queues"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached accessor — settings are read once and reused across the app."""
    return Settings()
