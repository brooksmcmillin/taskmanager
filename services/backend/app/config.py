"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
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

    # Validation constants
    min_password_length: int = 8
    min_client_secret_length: int = 32
    max_username_length: int = 50
    max_email_length: int = 255
    max_project_name_length: int = 100
    max_todo_title_length: int = 255


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
