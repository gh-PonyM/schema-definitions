"""Tests for settings module."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from schemi.settings import (
    DatabaseConfig,
    PostgresConnection,
    ProjectConfig,
    Settings,
    SqliteConnection,
)


def test_sqlite_config_valid():
    """Test valid SQLite configuration."""
    config = DatabaseConfig(
        type="sqlite",
        db_name="test_db",
        connection=SqliteConnection(db_path=Path("/path/to/db.sqlite"))
    )
    assert config.type == "sqlite"
    assert config.db_name == "test_db"
    assert isinstance(config.connection, SqliteConnection)


def test_postgres_config_valid():
    """Test valid PostgreSQL configuration."""
    config = DatabaseConfig(
        type="postgres",
        db_name="test_db",
        connection=PostgresConnection(
            host="localhost",
            port=5432,
            username="user",
            password="pass",
            database="test_db"
        )
    )
    assert config.type == "postgres"
    assert config.db_name == "test_db"
    assert isinstance(config.connection, PostgresConnection)


def test_db_name_with_spaces_invalid():
    """Test that db_name with spaces is invalid."""
    with pytest.raises(ValidationError, match="Database name cannot contain spaces"):
        DatabaseConfig(
            type="sqlite",
            db_name="test db",
            connection=SqliteConnection(db_path=Path("/path/to/db.sqlite"))
        )


def test_project_config_valid():
    """Test valid project configuration."""
    db_config = DatabaseConfig(
        type="sqlite",
        db_name="test_db",
        connection=SqliteConnection(db_path=Path("/path/to/db.sqlite"))
    )

    config = ProjectConfig(
        module="src/models.py",
        db={"staging": db_config}
    )

    assert config.module == Path("src/models.py")
    assert "staging" in config.db
    assert config.db["staging"] == db_config


def test_empty_settings_creation():
    """Test creating empty settings."""
    settings = Settings()
    assert settings.development is None
    assert settings.projects == {}


def test_settings_with_data(sample_settings_data):
    """Test creating settings with data."""
    settings = Settings(**sample_settings_data)

    assert settings.development is not None
    assert "sqlite" in settings.development.db
    assert "projectA" in settings.projects

    project = settings.projects["projectA"]
    assert project.module == Path("tests/fixtures/models.py")
    assert "staging" in project.db
    assert "prod" in project.db


def test_settings_load_creates_default(temp_settings_dir, monkeypatch):
    """Test that load creates default settings if file doesn't exist."""
    settings_path = temp_settings_dir / "test_settings.yaml"
    monkeypatch.setenv("SCHEMI_SETTINGS_PATH", str(settings_path))

    settings = Settings.load()

    assert isinstance(settings, Settings)
    assert settings.development is None
    assert settings.projects == {}
    assert settings_path.exists()


def test_settings_load_existing_file(cli_settings):
    """Test loading settings from existing file."""
    assert cli_settings.development is not None
    assert "projectA" in cli_settings.projects


def test_settings_save(cli_settings, temp_settings_dir):
    """Test saving settings to file."""
    settings_path = temp_settings_dir / "test_settings.yaml"
    cli_settings.save()

    assert settings_path.exists()

    # Load and verify
    with open(settings_path) as f:
        loaded_data = yaml.safe_load(f)

    assert "development" in loaded_data
    assert "projects" in loaded_data
    assert "projectA" in loaded_data["projects"]


def test_settings_path_from_env(temp_settings_dir, monkeypatch, sample_settings_data):
    """Test that settings path comes from environment variable."""
    custom_path = temp_settings_dir / "custom_settings.yaml"
    monkeypatch.setenv("SCHEMI_SETTINGS_PATH", str(custom_path))

    settings = Settings.load()
    settings.save()

    assert custom_path.exists()


def test_settings_default_path_unix(monkeypatch):
    """Test default settings path on Unix systems."""
    monkeypatch.delenv("SCHEMI_SETTINGS_PATH", raising=False)
    monkeypatch.setattr("platform.system", lambda: "Linux")

    path = Settings._get_settings_path()

    assert path.name == "settings.yaml"
    assert ".config/schemi" in str(path)


def test_settings_default_path_windows(monkeypatch):
    """Test default settings path on Windows."""
    monkeypatch.delenv("SCHEMI_SETTINGS_PATH", raising=False)
    monkeypatch.setattr("platform.system", lambda: "Windows")

    path = Settings._get_settings_path()

    assert path.name == "settings.yaml"
    assert "schemi" in str(path)
