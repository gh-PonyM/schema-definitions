"""Core business logic for schemi operations."""

from pathlib import Path
from typing import NamedTuple

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


def init_project(settings: Settings, project_name: str, force: bool = False, output_dir: str | None = None) -> InitResult:
    """Initialize migration folder for a project, creating project config if needed."""
    config_created = False

    # Check if project exists, if not create it
    if project_name not in settings.projects:
        # Use output directory if provided, otherwise current working directory
        base_dir = Path(output_dir) if output_dir else Path.cwd()
        module_dir = base_dir / project_name
        models_path = module_dir / "models.py"
        settings.projects[project_name] = ProjectConfig(
            module=str(models_path),
            db={}
        )
        settings.save()
        config_created = True

    project_config = settings.projects[project_name]
    module_path = Path(project_config.module)

    # Create migrations directory next to the module (always in the parent directory since module is a .py file)
    migrations_dir = module_path.parent / "migrations"

    if migrations_dir.exists() and not force:
        return InitResult(
            success=False,
            message=f"Migrations directory already exists at {migrations_dir}. Use --force to overwrite.",
            config_created=config_created,
            models_path=str(module_path)
        )

    # Create migrations directory structure
    migrations_dir.mkdir(parents=True, exist_ok=True)
    versions_dir = migrations_dir / "versions"
    versions_dir.mkdir(exist_ok=True)

    message_parts = []
    if config_created:
        message_parts.append(f"Config created in {settings._settings_path}")
    message_parts.append(f"Migration folder initialized at {migrations_dir}")

    return InitResult(
        success=True,
        message="\n".join(message_parts),
        config_created=config_created,
        models_path=str(module_path)
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
    import os
    import subprocess
    import tempfile
    from pathlib import Path

    module_path = Path(project_config.module)
    migrations_dir = module_path.parent / "migrations"
    versions_dir = migrations_dir / "versions"

    # Check if migrations directory exists
    if not migrations_dir.exists():
        return RevisionResult(
            success=False,
            message=f"Migrations directory not found at {migrations_dir}. Run 'schemi init' first."
        )

    # Create temporary alembic.ini file
    alembic_ini_content = f"""[alembic]
script_location = {migrations_dir}
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = sqlite:///:memory:
version_locations = {versions_dir}

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""

    # Create temporary env.py file
    env_py_content = f"""from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import sys
from pathlib import Path

# Add the project module to Python path
sys.path.insert(0, str(Path("{module_path}").parent))

# Import the models
try:
    from {Path(module_path).stem} import *
    from sqlmodel import SQLModel
    target_metadata = SQLModel.metadata
except ImportError:
    target_metadata = None

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={{"paramstyle": "named"}},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {{}}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
"""

    try:
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

    except Exception as e:
        return RevisionResult(
            success=False,
            message=f"Error creating revision: {e}"
        )
    finally:
        os.unlink(alembic_ini_path)
