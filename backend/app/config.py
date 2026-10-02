"""Application configuration.

All deployment-specific values are read from environment variables so that no
secrets live in source control. Sensible local-first defaults are provided so
the platform runs out of the box with `./dev.sh` or `docker compose up`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository paths. `backend/app/config.py` -> backend/ -> repo root.
APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
REPO_ROOT = BACKEND_DIR.parent
CHALLENGES_DIR = REPO_ROOT / "challenges"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CTF_",
        extra="ignore",
    )

    # General
    app_name: str = "Omar Web3 AI Security CTF"
    # "development" keeps /docs and verbose errors on. Anything else is treated
    # as production-like and hardens those surfaces (see plan section 16).
    environment: str = "development"

    # Database. Defaults to a file next to the backend package so SQLite data
    # survives restarts and lives on the mounted volume under Docker.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'ctf.db'}"

    # Server-side directory for generated plaintext flags (never in Git/DB/UI).
    # Overridden in Docker to live on the persistent volume.
    secrets_dir: str = str(BACKEND_DIR / ".secrets")

    # CORS: comma-separated list of allowed origins for the browser frontend.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Request hardening
    max_request_bytes: int = 16_384  # reject bodies larger than 16 KiB
    max_predict_text_length: int = 2_000  # per-field cap for inference input

    # Rate limiting (applied to the inference oracle endpoint)
    predict_rate_limit: str = "120/minute"

    # Default local player created automatically for the single-user MVP.
    default_player_id: str = "local-player"
    default_player_name: str = "Local Player"

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
