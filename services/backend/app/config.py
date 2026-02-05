"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root is three levels up from this file
# __file__ = services/backend/app/config.py
# .parent = services/backend/app
# .parent.parent = services/backend
# .parent.parent.parent = services
# .parent.parent.parent.parent = project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from shared .env file
    )

    # Database
    postgres_db: str = "taskmanager"
    postgres_user: str = "taskmanager"
    postgres_password: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        """Build async database URL with proper URL encoding."""
        from urllib.parse import quote_plus

        encoded_password = quote_plus(self.postgres_password)
        # Add SSL parameter to prefer SSL but allow non-SSL connections
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{encoded_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            f"?ssl=prefer"
        )

    # Security
    secret_key: str = "change-me-in-production"
    bcrypt_rounds: int = 12
    session_duration_days: int = 7

    # Rate limiting
    login_max_attempts: int = 5
    login_window_ms: int = 15 * 60 * 1000  # 15 minutes

    # OAuth
    access_token_expiry: int = 3600  # 1 hour in seconds
    auth_code_expiry: int = 10  # minutes
    device_code_expiry: int = 1800  # 30 minutes in seconds
    device_poll_interval: int = 5  # seconds

    # WebAuthn
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "TaskManager"
    webauthn_origin: str = "http://localhost:3000"
    webauthn_challenge_timeout: int = 300  # 5 minutes in seconds

    # Frontend URL (for OAuth consent page redirects)
    frontend_url: str = "http://localhost:3000"

    # CORS
    allowed_origins: str = ""

    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        if self.allowed_origins:
            return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]
        # Default origins
        return [
            "https://todo.brooksmcmillin.com",
            "https://todo2.brooksmcmillin.com",
            "http://localhost:4321",
            "http://localhost:3000",
        ]

    # Environment
    environment: str = "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    # Registration
    registration_code_required: bool = True

    # Validation constants
    min_password_length: int = 8
    min_client_secret_length: int = 32
    max_username_length: int = 50
    max_email_length: int = 255
    max_project_name_length: int = 100
    max_todo_title_length: int = 255

    # File uploads
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 10
    allowed_image_types: str = "image/jpeg,image/png,image/gif,image/webp"

    @property
    def upload_path(self) -> Path:
        """Get the upload directory as a Path object."""
        return Path(self.upload_dir)

    @property
    def max_upload_size_bytes(self) -> int:
        """Get max upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def allowed_image_types_list(self) -> list[str]:
        """Parse allowed image types from comma-separated string."""
        return [t.strip() for t in self.allowed_image_types.split(",") if t.strip()]

    @model_validator(mode="after")
    def validate_secret_key(self) -> "Settings":
        """Validate that secret key is not the default value in production."""
        if (
            self.is_production
            and self.secret_key == "change-me-in-production"  # pragma: allowlist secret
        ):
            raise ValueError(
                "SECRET_KEY must be changed in production. "
                "Generate a secure secret key and set it via the "
                "SECRET_KEY environment variable."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
