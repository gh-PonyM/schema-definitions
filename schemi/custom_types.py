from pathlib import Path
from urllib.parse import urlparse

import typer
from pydantic import PostgresDsn
from schemi.settings import DatabaseConfig, SqliteConnection, PostgresConnection


def parse_connection(value: str) -> "CliConnection":
    parsed = urlparse(value)
    if parsed.scheme == "sqlite":
        if not parsed.path:
            raise typer.BadParameter("SQLite URI must include a path")
        cfg = DatabaseConfig(
            type="sqlite", connection=SqliteConnection(db_path=Path(parsed.path))
        )

    elif parsed.scheme in {"postgresql", "postgres"}:
        try:
            dsn = PostgresDsn(value)
            host = dsn.hosts()[0]
        except Exception as err:
            raise typer.BadParameter(f"PostgreSQL URI invalid: {err}")
        cfg = DatabaseConfig(
            type="postgres",
            connection=PostgresConnection(
                host=host["host"],
                port=host["port"] or 5432,
                username=host["username"],
                password=host["password"] or "postgres",
                database=dsn.path.lstrip("/"),
            ),
        )
    else:
        raise typer.BadParameter(
            f"Unsupported scheme '{parsed.scheme}'. Only sqlite and postgresql/postgres are supported."
        )
    return CliConnection(cfg)


class CliConnection:
    def __init__(self, value):
        self.value: DatabaseConfig | None = value

    def __bool__(self):
        return bool(self.value)

    def __str__(self):
        t = self.value.type if self.value else "Emtpy"
        return f"DBConnection(type={t})"
