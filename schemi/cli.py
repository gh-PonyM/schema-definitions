"""Main CLI application for schemi."""

from typing import Annotated
from pathlib import Path
import typer

from .core import clone_database, create_revision, init_project, migrate_database
from .settings import Settings
from .validation import (
    validate_matching_db_types,
    validate_project_environment,
    validate_project_exists,
)

app = typer.Typer(
    name="schemi",
    help="A command line tool for managing database schemas and migrations",
    no_args_is_help=True,
    pretty_exceptions_enable=False
)


@app.callback()
def main(
    ctx: typer.Context,
    settings_path: Annotated[
        str | None,
        typer.Option(
            "--settings-path",
            "-s",
            help="Path to settings file (overrides SCHEMI_SETTINGS_PATH env var)",
            envvar="SCHEMI_SETTINGS_PATH",
        ),
    ] = None,
):
    """Schemi: Database schema and migration management tool."""
    if settings_path:
        import os
        os.environ["SCHEMI_SETTINGS_PATH"] = settings_path

    settings = Settings.load()
    ctx.ensure_object(dict)
    ctx.obj["settings"] = settings


@app.command()
def init(
    ctx: typer.Context,
    project_name: Annotated[str, typer.Argument(help="Name of the project to initialize")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Overwrite existing migration files")] = False,
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output directory for project files")] = None,
):
    """Initialize migration folder for a project."""
    settings: Settings = ctx.obj["settings"]

    result = init_project(settings, project_name, force, output)

    if result.success:
        typer.secho(result.message, fg=typer.colors.GREEN)
    else:
        typer.secho(f"Error: {result.message}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def migrate(
    ctx: typer.Context,
    target: Annotated[str, typer.Argument(help="Target in format 'project.environment'")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be done without executing")] = False,
    message: Annotated[str | None, typer.Option("--message", "-m", help="Migration message")] = None,
    revision: Annotated[str | None, typer.Option("--revision", help="Target revision")] = None,
):
    """Run database migrations."""
    settings: Settings = ctx.obj["settings"]

    pe = validate_project_environment(settings, target)
    result = migrate_database(pe.project_config, pe.db_config, dry_run, message, revision)

    if result.success:
        color = typer.colors.YELLOW if dry_run else typer.colors.GREEN
        typer.secho(result.message, fg=color)
    else:
        typer.secho(f"Error: {result.message}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def clone(
    ctx: typer.Context,
    source: Annotated[str, typer.Argument(help="Source database in format 'project.environment'")],
    target: Annotated[str, typer.Argument(help="Target database in format 'project.environment'")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be done without executing")] = False,
):
    """Clone database from source to target (same database type only)."""
    settings: Settings = ctx.obj["settings"]

    src_pe = validate_project_environment(settings, source)
    tgt_pe = validate_project_environment(settings, target)
    validate_matching_db_types(src_pe.db_config, tgt_pe.db_config)

    result = clone_database(src_pe.db_config, tgt_pe.db_config, dry_run)

    if result.success:
        color = typer.colors.YELLOW if dry_run else typer.colors.GREEN
        typer.secho(result.message, fg=color)
    else:
        typer.secho(f"Error: {result.message}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)


@app.command()
def revision(
    ctx: typer.Context,
    project_name: Annotated[str, typer.Argument(help="Name of the project to create revision for")],
    message: Annotated[str, typer.Option("--message", "-m", help="Revision message")] = "Auto-generated revision",
    autogenerate: Annotated[bool, typer.Option("--autogenerate", help="Auto-generate migration from model changes")] = True,
):
    """Create a new migration revision."""
    settings: Settings = ctx.obj["settings"]

    project_config = validate_project_exists(settings, project_name)
    result = create_revision(project_config, message, autogenerate)

    if result.success:
        typer.secho(result.message, fg=typer.colors.GREEN)
        if result.revision_file:
            typer.secho(f"Revision file: {result.revision_file}", fg=typer.colors.BLUE)
    else:
        typer.secho(f"Error: {result.message}", err=True, fg=typer.colors.RED)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
