"""Settings models for schema management."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, PrivateAttr
from urllib.parse import quote_plus

from schemi.constants import DEFAULT_SETTINGS_FN, DEFAULT_DEV_DB_NAME


class SqliteConnection(BaseModel):
    """SQLite database connection configuration."""

    db_path: Path

    @property
    def get_dsn(self) -> str:
        """Get SQLAlchemy DSN for SQLite connection."""
        return f"sqlite:///{self.db_path}"


class PostgresConnection(BaseModel):
    """PostgreSQL database connection configuration."""

    host: str = "127.0.0.1"
    port: int = 5432
    username: str = "postgres"
    database: str = "postgres"
    password: str = "postgres"

    @property
    def get_dsn(self) -> str:
        """Get SQLAlchemy DSN for PostgreSQL connection."""
        # URL encode the password to handle special characters
        encoded_password = quote_plus(self.password)
        return f"postgresql://{self.username}:{encoded_password}@{self.host}:{self.port}/{self.database}"

    @field_validator("database")
    @classmethod
    def validate_db_name(cls, v: str) -> str:
        if " " in v:
            raise ValueError("Database name cannot contain spaces")
        return v



class DatabaseConfig(BaseModel):
    """Database configuration for a specific environment."""

    type: Literal["sqlite", "postgres"]
    connection: SqliteConnection | PostgresConnection

    @property
    def db_name(self):
        return getattr(self.connection, "database", self.connection.db_path)


class ProjectConfig(BaseModel):
    """Configuration for a specific project."""

    module: Path = Field(..., description="Path to Python module containing SQLModel definitions")
    db: dict[str, DatabaseConfig] = Field(..., description="Database environments")


def default_dev_config():
    return {"sqlite": DatabaseConfig(type="sqlite", connection=SqliteConnection(db_path=DEFAULT_DEV_DB_NAME))}


class DevelopmentConfig(BaseModel):
    """Development database configuration."""

    db: dict[str, DatabaseConfig] = Field(default_factory=default_dev_config)


def default_settings_path() -> Path:
    return Path(".") / DEFAULT_SETTINGS_FN



class Settings(BaseModel):
    """Main settings configuration."""

    development: DevelopmentConfig | None = None
    projects: dict[str, ProjectConfig] = Field(default_factory=dict)

    _settings_path: Path | None = PrivateAttr(default_factory=default_settings_path)

    @classmethod
    def from_file(cls, settings_path: Path) -> "Settings":
        """Load settings from file."""
        if not settings_path.exists():
            # Create default settings file
            settings = cls()
            settings._settings_path = settings_path
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
