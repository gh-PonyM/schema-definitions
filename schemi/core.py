"""Core business logic for schemi operations."""

from pathlib import Path
from typing import NamedTuple
import importlib
import inspect
from functools import lru_cache
import shutil
from .settings import DatabaseConfig, ProjectConfig, Settings


class InitResult(NamedTuple):
    """Result of initialization operation."""
    success: bool
    message: str
    config_created: bool = False
    models_path: str | None = None


class MigrateResult(NamedTuple):
    """Result of migration operation."""
    success: bool
    message: str


class CloneResult(NamedTuple):
    """Result of clone operation."""
    success: bool
    message: str


class RevisionResult(NamedTuple):
    """Result of revision creation operation."""
    success: bool
    message: str
    revision_file: str | None = None



@lru_cache(maxsize=32)
def module_path_root(module: str):
    if isinstance(module, str):
        module = importlib.import_module(module)

    assert module is not None
    return Path(inspect.getfile(module)).parents[0]

templates_path = module_path_root("schemi") / "templates"

def init_project(settings: Settings, project_name: str, force: bool = False, output_dir: Path | None = None) -> InitResult:
    """Initialize migration folder for a project, creating project config if needed."""
    config_created = False

    # Check if project exists, if not create it
    if output_dir:
        project_dir = output_dir.resolve() / project_name
    else:
        project_dir = Path.cwd().resolve() / project_name

    models_path = project_dir / "models.py"
    if project_name not in settings.projects:
        # Use output directory if provided, otherwise current working directory
        settings.projects[project_name] = ProjectConfig(
            module=models_path,
            db={}
        )
        config_created = True
    else:
      settings.projects[project_name].module = models_path
    settings.save()
    # project_config = settings.projects[project_name]

    # Create migrations directory next to the module (always in the parent directory since module is a .py file)
    migrations_dir = project_dir / "migrations"
    if migrations_dir.exists() and not force:
        return InitResult(
            success=False,
            message=f"Migrations directory already exists at {migrations_dir}. Use --force to overwrite.",
            config_created=config_created,
            models_path=str(project_dir)
        )

    # Create migrations directory structure
    migrations_dir.mkdir(parents=True, exist_ok=True)
    versions_dir = migrations_dir / "versions"
    versions_dir.mkdir(exist_ok=True)

    # Create script.py.mako template for alembic
    script_template = (templates_path / "script.py.mako")
    script_template_path = migrations_dir / "script.py.mako"
    shutil.copy2(script_template, script_template_path)
    message_parts = []
    if config_created:
        message_parts.append(f"Config created in {settings._settings_path}")
    message_parts.append(f"Migration folder initialized at {migrations_dir}")
    if not models_path.is_file():
        models_path.write_text("# Put your SQLModels in here\n\n")

    return InitResult(
        success=True,
        message="\n".join(message_parts),
        config_created=config_created,
        models_path=str(models_path)
    )


def migrate_database(
    project_config: ProjectConfig,
    db_config: DatabaseConfig,
    dry_run: bool = False,
    message: str | None = None,
    revision: str | None = None
) -> MigrateResult:
    """Run database migrations."""
    # TODO: Implement actual alembic integration
    action = "[DRY RUN] Would migrate" if dry_run else "Migrated"
    return MigrateResult(
        success=True,
        message=f"{action} database '{db_config.db_name}' ({db_config.type})"
    )


def clone_database(
    src_db_config: DatabaseConfig,
    tgt_db_config: DatabaseConfig,
    dry_run: bool = False
) -> CloneResult:
    """Clone database from source to target (assumes same type already validated)."""
    # TODO: Implement actual database cloning logic
    action = "[DRY RUN] Would clone" if dry_run else "Cloned"
    return CloneResult(
        success=True,
        message=f"{action} {src_db_config.db_name} to {tgt_db_config.db_name} ({src_db_config.type})"
    )


def create_revision(
    project_config: ProjectConfig,
    message: str,
    autogenerate: bool = True
) -> RevisionResult:
    """Create a new migration revision using alembic."""
    import subprocess
    import tempfile
    import os

    models_path = project_config.module.absolute()
    migrations_dir = models_path.parent / "migrations"
    versions_dir = migrations_dir / "versions"

    # Check if migrations directory exists
    if not migrations_dir.exists():
        return RevisionResult(
            success=False,
            message=f"Migrations directory not found at {migrations_dir}. Run 'schemi init' first."
        )

    # Create temporary alembic.ini file
    alembic_ini_content = (templates_path / "alembic.ini").read_text()
    alembic_ini_content = alembic_ini_content.format(
        migrations_dir=str(migrations_dir),
        versions_dir=str(versions_dir)
        )

    # Create temporary env.py file
    env_py_content = (templates_path / "env.py").read_text()
    env_py_content = env_py_content.format(
    models_path=models_path,
    models_import_path=models_path.stem,
    )
    # Create temporary files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(alembic_ini_content)
        alembic_ini_path = f.name

    # Write env.py to migrations directory
    env_py_path = migrations_dir / "env.py"
    with open(env_py_path, 'w') as f:
        f.write(env_py_content)

    # Run alembic revision command
    cmd = ['alembic', '-c', alembic_ini_path, 'revision']
    if autogenerate:
        cmd.append('--autogenerate')
    cmd.extend(['-m', message])

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(migrations_dir.parent)
    )
    if result.returncode != 0:
        return RevisionResult(
            success=False,
            message=f"Alembic revision failed: {result.stderr}"
        )

    # Find the created revision file
    revision_files = list(versions_dir.glob("*.py"))
    latest_revision = max(revision_files, key=lambda p: p.stat().st_mtime, default=None)

    return RevisionResult(
        success=True,
        message=f"Created revision: {message}",
        revision_file=str(latest_revision) if latest_revision else None
    )
    os.unlink(alembic_ini_path)
