"""Validation helpers and custom types for CLI."""

from typing import NamedTuple

import typer

from .settings import DatabaseConfig, ProjectConfig, Settings


class ProjectEnvironment(NamedTuple):
    """Parsed project.environment target."""

    project_name: str
    environment_name: str
    project_config: ProjectConfig
    db_config: DatabaseConfig


def validate_project_environment(settings: Settings, target: str) -> ProjectEnvironment:
    """Validate and parse project.environment format."""
    try:
        project_name, env_name = target.split(".", 1)
    except ValueError:
        typer.secho(
            "Error: Target must be in format 'project.environment'",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    if project_name not in settings.projects:
        typer.secho(
            f"Error: Project '{project_name}' not found in settings",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    project_config = settings.projects[project_name]
    if env_name not in project_config.db:
        typer.secho(
            f"Error: Environment '{env_name}' not found in project '{project_name}'",
            err=True,
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    return ProjectEnvironment(
        project_name=project_name,
        environment_name=env_name,
        project_config=project_config,
        db_config=project_config.db[env_name],
    )


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
