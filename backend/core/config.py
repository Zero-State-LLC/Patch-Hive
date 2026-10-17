"""
Core configuration for PatchHive backend.
Uses pydantic-settings for environment-based configuration.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "PatchHive"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Database
    database_url: str = "postgresql://patchhive:***@localhost:5432/patchhive"
    database_echo: bool = False
    # Dev/sqlite escape hatch only. Deploy/staging must use alembic upgrade head.
    allow_create_all: bool = False

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # CORS — accepts JSON list or comma-separated env (docker-compose style).
    # NoDecode: pydantic-settings otherwise JSON-parses list env before validators.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # Frontend
    frontend_base_url: str = "http://localhost:5173"

    # Canonical scope gates. Historical surfaces are off unless explicitly enabled.
    enable_legacy_social: bool = False
    enable_legacy_publishing: bool = False
    enable_legacy_leaderboards: bool = False
    enable_legacy_referrals: bool = False

    # Decision Intelligence. Provider integration remains fail-closed by default.
    enable_decision_intelligence: bool = False
    decision_provider: str = "disabled"
    typesafe_api_key: str = ""
    jev_base_url: str = "https://api.typesafe.ai"
    jev_model: str = ""
    decision_auto_propose_at: float = 0.90
    decision_user_review_at: float = 0.65
    decision_probability_margin: float = 0.10

    # Patch Engine
    patch_engine_version: str = "1.0.0"
    # Compatibility alias used by some call sites / older tests.
    generation_version: str = "1.0.0"
    max_patches_per_generation: int = 20
    default_generation_seed: int = 42
    patchbook_export_cost: int = 3
    # Legacy POST /api/export/runs/{id}/patchbook debit path (transitional).
    # MVP UI and acceptance use /api/canon/exports; set false to hard-disable debit.
    enable_legacy_patchbook_debit: bool = False
    stripe_test_mode: bool = True
    allow_production_payments: bool = False
    # Empty defaults: development may derive local secrets; production policy enforces real ones.
    stripe_webhook_secret: str = ""
    download_token_secret: str = ""

    # File Storage
    export_dir: str = "./exports"
    export_store_root: str = "./exports"
    waveform_dir: str = "./waveforms"

    # PatchBook Design Engine (presentation layer; defaults off — no behavior change)
    enable_patchbook_design_engine: bool = False
    enable_canon_export_fulfillment: bool = False
    enable_inline_export_fulfillment: bool = False
    enable_patchbook_publication_profile: bool = False
    require_sealed_generated_patches: bool = False
    design_engine_default_tier: str = "core"
    export_fulfill_max_attempts: int = 5
    preview_rate_limit_per_minute: int = 30

    # ABX-Core / SEED
    abx_core_version: str = "1.3"
    enforce_seed_traceability: bool = True

    # Test mode
    test_mode: bool = False

    # Git tracking (optional, for provenance)
    git_commit: str = ""  # Set by environment or CI/CD

    @field_validator("decision_provider")
    @classmethod
    def _validate_decision_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"disabled", "jev"}:
            raise ValueError("decision_provider must be 'disabled' or 'jev'")
        return normalized

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return ["http://localhost:5173", "http://localhost:3000"]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                parsed = json.loads(text)
                if not isinstance(parsed, list):
                    raise ValueError("cors_origins JSON must be a list of strings")
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [part.strip() for part in text.split(",") if part.strip()]
        raise ValueError(f"Unsupported cors_origins type: {type(value)!r}")


# Global settings instance
settings = Settings()
