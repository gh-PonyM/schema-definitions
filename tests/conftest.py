import shutil
import tempfile
from pathlib import Path
from traceback import print_tb

import pytest
from typer.testing import CliRunner as BaseCliRunner

from schemi.constants import SETTINGS_PATH_ENV_VAR
from schemi.settings import Settings


class CliRunner(BaseCliRunner):
    with_traceback = True

    def invoke(self, cli, commands, **kwargs):
        result = super().invoke(cli, commands, **kwargs)
        if not result.exit_code == 0 and self.with_traceback:
            print_tb(result.exc_info[2])
            print(result.exception)
            print(result.stderr)
        return result


@pytest.fixture
def temp_settings_dir():
    """Create a temporary directory for settings."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def cli_settings_path(temp_settings_dir, monkeypatch):
    """Create settings for CLI testing with environment variable set."""
    settings_path = temp_settings_dir / "test_settings.yaml"
    monkeypatch.setenv(SETTINGS_PATH_ENV_VAR, str(settings_path))
    return settings_path


@pytest.fixture
def cli_settings(cli_settings_path, monkeypatch, sample_settings_data):
    """Create settings for CLI testing with environment variable set."""
    # Return loaded settings instance
    s = Settings(**sample_settings_data)
    s._settings_path = cli_settings_path
    s.save()
    return s


@pytest.fixture
def sample_settings_data(temp_settings_dir):
    """Sample settings data for testing."""
    return {
        "development": {
            "db": {
                "projectA": {
                    "type": "sqlite",
                    "connection": {
                        "db_path": str(temp_settings_dir / "schemi-dev.sqlite")
                    },
                },
                "pglocal": {
                    "type": "postgres",
                    "connection": {
                        "host": "localhost",
                        "port": 5432,
                        "username": "dev",
                        "password": "dev_pass",
                        "database": "dev_db",
                    },
                },
            }
        },
        "projects": {
            "projectA": {
                "module": "tests/fixtures/models.py",
                "db": {
                    "staging": {
                        "type": "sqlite",
                        "connection": {
                            "db_path": str(temp_settings_dir / "staging.sqlite")
                        },
                    },
                    "prod": {
                        "type": "postgres",
                        "connection": {
                            "host": "prod.example.com",
                            "port": 5432,
                            "username": "prod_user",
                            "password": "prod_pass",
                            "database": "prod_db",
                        },
                    },
                },
            }
        },
    }


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()
