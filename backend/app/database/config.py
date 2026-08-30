"""Runtime configuration sourced from the environment."""

import os
from pathlib import Path


def _load_local_env() -> None:
    """Load the small local development .env file without an extra dependency."""
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/nurse_schedule_db")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "development-only-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
FRONTEND_ORIGINS = [origin.strip() for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
STAFF_INITIAL_PASSWORD = os.getenv("STAFF_INITIAL_PASSWORD")
ADMIN_INITIAL_PASSWORD = os.getenv("ADMIN_INITIAL_PASSWORD")


def _require_strong_secret(name: str, value: str | None, minimum_length: int) -> None:
    if not value or len(value) < minimum_length:
        raise RuntimeError(f"{name} must be at least {minimum_length} characters in production")


def validate_runtime_config() -> None:
    """Refuse unsafe defaults in a production process."""
    if ENVIRONMENT == "production":
        _require_strong_secret("JWT_SECRET_KEY", JWT_SECRET_KEY, 32)
        if "postgres:postgres@" in DATABASE_URL:
            raise RuntimeError("DATABASE_URL must not use the development default in production")
        _require_strong_secret("ADMIN_INITIAL_PASSWORD", ADMIN_INITIAL_PASSWORD, 12)
        _require_strong_secret("STAFF_INITIAL_PASSWORD", STAFF_INITIAL_PASSWORD, 12)
