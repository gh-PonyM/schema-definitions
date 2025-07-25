"""Validation helpers and custom types for CLI."""

import typer

from .settings import DatabaseConfig, ProjectConfig, Settings


def validate_project_exists(settings: Settings, project_name: str) -> ProjectConfig:
    """Validate that project exists in settings."""
    if project_name not in settings.projects:
        typer.secho(
            f"Error: Project '{project_name}' not found in settings",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    return settings.projects[project_name]


def validate_matching_db_types(src_db: DatabaseConfig, tgt_db: DatabaseConfig) -> None:
    """Validate that database types match."""
    if src_db.type != tgt_db.type:
        typer.secho(
            f"Error: Database types must match (source: {src_db.type}, target: {tgt_db.type})",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
