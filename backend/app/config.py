"""
Environment configuration with fail-fast validation.

Required vars fail at startup if missing.
Optional vars degrade gracefully — citation intel works with
fewer sources if some API keys are absent.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # === Required (fail-fast if missing) ===
    database_url: str = Field(
        ...,
        description="PostgreSQL connection string (asyncpg)",
    )
    auth_secret: str = Field(
        ...,
        description="Shared secret for HS256 JWT verification",
    )
    perplexity_api_key: str = Field(
        ...,
        description="Perplexity API key for citation URL discovery",
    )

    # === Optional (degrade gracefully if absent) ===
    semantic_scholar_api_key: Optional[str] = Field(
        default=None,
        description=(
            "Semantic Scholar partner API key for higher rate limits (10 req/sec). "
            "Works without it on free tier (1 req/sec)."
        ),
    )
    # arXiv requires no key

    # === Optional with defaults ===
    daily_run_limit: int = Field(
        default=10,
        description="Maximum discovery runs per day across all users",
    )
    allowed_origins: str = Field(
        default="http://localhost:3000",
        description="Comma-separated list of allowed CORS origins",
    )
    env: str = Field(
        default="development",
        description="Environment: development, staging, production",
    )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins(self) -> list[str]:
        """Parse allowed origins from comma-separated string."""
        origins = [o.strip() for o in self.allowed_origins.split(",")]
        if self.env == "development":
            origins.extend([
                "http://localhost:3000",
                "http://localhost:3001",
                "http://localhost:3005",
            ])
        return list(set(origins))

    @property
    def async_database_url(self) -> str:
        """Convert postgresql:// to postgresql+asyncpg:// for async driver."""
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    @property
    def semantic_scholar_rate_limit(self) -> tuple[int, float]:
        """Returns (max_concurrent, sleep_between_requests) based on key presence."""
        if self.semantic_scholar_api_key:
            return (10, 0.1)
        return (1, 1.0)


def get_settings() -> Settings:
    """Create and validate settings. Fails fast on missing required vars."""
    return Settings()  # type: ignore[call-arg]
