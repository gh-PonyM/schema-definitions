from enum import Enum
from typing import Annotated
from pathlib import Path
import typer

from schemi.custom_types import CliConnection, parse_connection
from .core import clone_database, create_revision, init_project, migrate_database
from .settings import Settings, default_settings_path
from .validation import (
    validate_matching_db_types,
    validate_project_environment,
)
from .constants import SETTINGS_PATH_ENV_VAR, PROG_NAME

app = typer.Typer(
    name=PROG_NAME,
    help="A command line tool for managing database schemas and migrations",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


def success(msg: str, dry_run: bool = False):
    color = typer.colors.YELLOW if dry_run else typer.colors.GREEN
    typer.secho(msg, fg=color)


def error(msg: str):
    typer.secho(f"Error: {msg}", err=True, fg=typer.colors.RED)


@app.callback()
def main(
    ctx: typer.Context,
    settings_path: Annotated[
        Path | None,
        typer.Option(
            "--settings-path",
            "-s",
            help=f"Path to settings file (or use env {SETTINGS_PATH_ENV_VAR} env var)",
            envvar=SETTINGS_PATH_ENV_VAR,
            default_factory=default_settings_path,
        ),
    ],
):
    """Database schema and migration management tool."""
    settings = Settings.from_file(settings_path)
    ctx.ensure_object(dict)
    ctx.obj["settings"] = settings


ConnectionCliType = Annotated[
    CliConnection,
    typer.Option(
        "--connection",
        "-c",
        help="Examples: sqlite:/opt/site.db | postgres://user:pw@localhost:5432/db_name",
        parser=parse_connection,
    ),
]


class CliDBType(str, Enum):
    sqlite = "sqlite"
    pg = "postgres"


@app.command()
def init(
    ctx: typer.Context,
    project_name: Annotated[
        str, typer.Argument(help="Name of the project to initialize")
    ],
    env: Annotated[
        str, typer.Option("--env", "-e", help="Environment for connection")
    ] = "prod",
    connection: ConnectionCliType = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing migration files")
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output directory for project files"),
    ] = None,
    dev_db_type: Annotated[
        CliDBType, typer.Option(help="Database used local development")
    ] = CliDBType.sqlite,
):
    """Initialize migration folder for a project."""
    settings: Settings = ctx.obj["settings"]
    result = init_project(
        settings,
        project_name,
        force,
        output,
        connection.value if connection else None,
        env,
        dev_db_type=dev_db_type.value,
    )

    if result.success:
        success(result.message)
    else:
        error(result.message)
        raise typer.Exit(1)


TargetType = Annotated[
    str, typer.Argument(help="Target in format 'project.environment'")
]


@app.command()
def migrate(
    ctx: typer.Context,
    target: TargetType,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without executing"),
    ] = False,
    message: Annotated[
        str | None, typer.Option("--message", "-m", help="Migration message")
    ] = None,
    revision: Annotated[
        str | None, typer.Option("--revision", help="Target revision")
    ] = None,
):
    """Run database migrations."""
    settings: Settings = ctx.obj["settings"]

    pe = validate_project_environment(settings, target)
    result = migrate_database(
        pe.project_config, pe.db_config, dry_run, message, revision
    )

    if result.success:
        success(result.message, dry_run)
    else:
        typer.secho(f"Error: {result.message}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def clone(
    ctx: typer.Context,
    source: Annotated[
        str, typer.Argument(help="Source database in format 'project.environment'")
    ],
    target: TargetType,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be done without executing"),
    ] = False,
):
    """Clone database from source to target (same database type only)."""
    settings: Settings = ctx.obj["settings"]

    src_pe = validate_project_environment(settings, source)
    tgt_pe = validate_project_environment(settings, target)
    validate_matching_db_types(src_pe.db_config, tgt_pe.db_config)

    result = clone_database(src_pe.db_config, tgt_pe.db_config, dry_run)

    if result.success:
        success(result.message)
    else:
        error(result.message)
        raise typer.Exit(1)


@app.command()
def revision(
    ctx: typer.Context,
    target: TargetType,
    message: Annotated[
        str, typer.Option("--message", "-m", help="Revision message")
    ] = "Auto-generated revision",
    autogenerate: Annotated[
        bool,
        typer.Option(
            "--autogenerate/--no-autogenerate",
            help="Auto-generate migration from model changes",
        ),
    ] = True,
):
    """Create a new migration revision."""
    settings: Settings = ctx.obj["settings"]

    p_env = validate_project_environment(settings, target)
    result = create_revision(
        p_env.project_config, p_env.db_config, message, autogenerate
    )

    if result.success:
        success(result.message)
        if result.revision_file:
            typer.secho(f"Revision file: {result.revision_file}", fg=typer.colors.BLUE)
    else:
        error(result.message)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
