"""Settings models for schema management."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator
import typer

DEFAULT_SETTINGS_FN = "settings.yaml"


class SqliteConnection(BaseModel):
    """SQLite database connection configuration."""

    db_path: Path


class PostgresConnection(BaseModel):
    """PostgreSQL database connection configuration."""

    host: str = "127.0.0.1"
    port: int = 5432
    username: str = "postgres"
    database: str = "postgres"
    password: str = "postgres"


class DatabaseConfig(BaseModel):
    """Database configuration for a specific environment."""

    type: Literal["sqlite", "postgres"]
    db_name: str = Field(..., description="Database name (no spaces allowed)")
    connection: SqliteConnection | PostgresConnection

    @field_validator("db_name")
    @classmethod
    def validate_db_name(cls, v: str) -> str:
        """Validate that db_name contains no spaces."""
        if " " in v:
            raise ValueError("Database name cannot contain spaces")
        return v


class ProjectConfig(BaseModel):
    """Configuration for a specific project."""

    module: Path = Field(..., description="Path to Python module containing SQLModel definitions")
    db: dict[str, DatabaseConfig] = Field(..., description="Database environments")


class DevelopmentConfig(BaseModel):
    """Development database configuration."""

    db: dict[str, str | DatabaseConfig] = Field(default_factory=dict)


class Settings(BaseModel):
    """Main settings configuration."""

    development: DevelopmentConfig | None = None
    projects: dict[str, ProjectConfig] = Field(default_factory=dict)

    _settings_path: Path | None = None

    def __init__(self, **data):
        super().__init__(**data)
        self._settings_path = self._get_settings_path()

    @staticmethod
    def _get_settings_path() -> Path:
        """Get the settings file path from environment or default location."""
        import os
        env_path = os.getenv("SCHEMI_SETTINGS_PATH")
        if env_path:
            return Path(env_path)

        config_dir = Path(typer.get_app_dir("schemi"))
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / DEFAULT_SETTINGS_FN

    @classmethod
    def load(cls, settings_path: Path | None = None) -> "Settings":
        """Load settings from file."""
        settings_path = settings_path or cls._get_settings_path()

        if not settings_path.exists():
            # Create default settings file
            settings = cls()
            settings.save()
            return settings

        with open(settings_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        settings = cls(**data)
        settings._settings_path = settings_path
        return settings

    def save(self) -> None:
        """Save settings to file."""
        if not self._settings_path:
            self._settings_path = self._get_settings_path()

        # Ensure directory exists
        self._settings_path.parent.mkdir(exist_ok=True)

        # Re-validate
        data_dump = self.model_dump(exclude={"_settings_path"}, mode="json")
        self.__class__(**data_dump)
        with open(self._settings_path, "w", encoding="utf-8") as f:
            yaml.dump(data_dump, f, default_flow_style=False, indent=2)
