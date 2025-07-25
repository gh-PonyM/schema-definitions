import contextlib
import tempfile
from pathlib import Path
from typing import NamedTuple
import importlib
import inspect
from functools import lru_cache
import shutil

from .constants import PROG_NAME
from .settings import DatabaseConfig, ProjectConfig, Settings, DBType


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
    sql: str | None = None


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


templates_path = module_path_root(PROG_NAME) / "templates"


def init_project(
    settings: Settings,
    project_name: str,
    force: bool = False,
    output_dir: Path | None = None,
    db_config: DatabaseConfig | None = None,
    env_name: str = "prod",
    dev_db_type: DBType = "sqlite",
) -> InitResult:
    """Initialize migration folder for a project, creating project config if needed."""
    config_created = False

    # Check if project exists, if not create it
    if output_dir:
        project_dir = output_dir.resolve() / project_name
    else:
        project_dir = Path.cwd().resolve() / project_name

    models_path = project_dir / "models.py"
    if project_name not in settings.projects:
        config_created = True
    project_config = settings.add_project(project_name, models_path)
    if db_config:
        project_config.db[env_name] = db_config
    settings.development.add_connection(project_name, db_type=dev_db_type)
    settings.save()

    # Create migrations directory next to the module (always in the parent directory since module is a .py file)
    migrations_dir = project_dir / "migrations"
    if migrations_dir.exists() and not force:
        return InitResult(
            success=False,
            message=f"Migrations directory already exists at {migrations_dir}. Use --force to overwrite.",
            config_created=config_created,
            models_path=str(project_dir),
        )

    # Create migrations directory structure
    migrations_dir.mkdir(parents=True, exist_ok=True)
    versions_dir = migrations_dir / "versions"
    versions_dir.mkdir(exist_ok=True)
    dev_db = settings.development.db[project_name].db_name

    message_parts = []
    if config_created:
        message_parts.append(f"Config created in {settings._settings_path}")
    message_parts.append(
        f"Migration folder initialized at {migrations_dir} and development db '{dev_db}' added"
    )
    if db_config:
        message_parts.append("Added prod db for project")
    if not models_path.is_file():
        models_path.write_text("# Put your SQLModels in here\n\n")

    return InitResult(
        success=True,
        message="\n".join(message_parts),
        config_created=config_created,
        models_path=str(models_path),
    )


def clone_database(
    src_db_config: DatabaseConfig, tgt_db_config: DatabaseConfig, dry_run: bool = False
) -> CloneResult:
    """Clone database from source to target (assumes same type already validated)."""
    # TODO: Implement actual database cloning logic
    action = "[DRY RUN] Would clone" if dry_run else "Cloned"
    return CloneResult(
        success=True,
        message=f"{action} {src_db_config.db_name} to {tgt_db_config.db_name} ({src_db_config.type})",
    )


@contextlib.contextmanager
def create_temp_dir():
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir)


def create_alembic_temp_files(tmp: Path, models_path: Path, versions_dir: Path) -> None:
    # Create temporary alembic.ini file
    alembic_ini_content = (templates_path / "alembic.ini").read_text()
    # Create temporary env.py file
    env_py_content = (templates_path / "env.py").read_text()
    env_py_content = env_py_content.format(
        models_path=models_path,
        models_import_path=models_path.stem,
    )
    # Create temporary files

    alembic_ini_path = tmp / "alembic.ini"
    alembic_script_dir = tmp
    alembic_ini_content = alembic_ini_content.format(
        script_dir=str(alembic_script_dir), versions_dir=str(versions_dir)
    )
    alembic_ini_path.write_text(alembic_ini_content)

    # Write env.py to script_location directory
    env_py_path = alembic_script_dir / "env.py"
    env_py_path.write_text(env_py_content)

    script_template = templates_path / "script.py.mako"
    script_template_path = alembic_script_dir / script_template.name
    shutil.copy2(script_template, script_template_path)


def run_alembic(cmd: list[str], project_cfg: ProjectConfig, db_config: DatabaseConfig):
    import subprocess
    import os

    with create_temp_dir() as tmp:
        create_alembic_temp_files(tmp, project_cfg.module, project_cfg.versions_dir)
        # Run alembic revision command
        cmd = ["alembic", "-c", str(tmp / "alembic.ini"), *cmd]
        os.environ["SCHEMI_CURRENT_DSN"] = db_config.connection.get_dsn
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(project_cfg.migrations_dir.parent),
        )


def create_revision(
    project_config: ProjectConfig,
    db_config: DatabaseConfig,
    message: str,
    autogenerate: bool = True,
) -> RevisionResult:
    """Create a new migration revision using alembic."""
    models_path = project_config.module.absolute()
    migrations_dir = project_config.migrations_dir
    versions_dir = project_config.versions_dir

    # Check if migrations directory exists
    if not migrations_dir.exists():
        return RevisionResult(
            success=False,
            message=f"Migrations directory not found at {migrations_dir}. Run '{PROG_NAME} init' first.",
        )
    cmd = ["revision", "-m", message]
    if autogenerate:
        cmd.append("--autogenerate")
    result = run_alembic(cmd, project_config, db_config)
    if result.returncode != 0:
        return RevisionResult(
            success=False, message=f"Alembic revision failed: {result.stderr}"
        )
    # Find the created revision file
    revision_files = list(versions_dir.glob("*.py"))
    latest_revision = max(revision_files, key=lambda p: p.stat().st_mtime, default=None)
    return RevisionResult(
        success=True,
        message=f"Created revision: {message}",
        revision_file=str(latest_revision) if latest_revision else None,
    )


def migrate_database(
    project_config: ProjectConfig,
    db_config: DatabaseConfig,
    dry_run: bool = False,
    message: str | None = None,
    revision: str = "HEAD",
) -> MigrateResult:
    """Run database migrations."""
    # TODO: Implement actual alembic integration
    cmd = ["upgrade", revision]
    if dry_run:
        # Does not apply migration to db, but emits sql to stdout
        cmd.append("--sql")
    result = run_alembic(cmd, project_config, db_config)
    if result.returncode != 0:
        return MigrateResult(
            success=False,
            message=f"Failed to run alembic migrations ‘{db_config.db_name}’ ({db_config.type})",
            sql=result.stdout.strip() if dry_run else None,
        )
    action = "[DRY RUN] Would migrate" if dry_run else "Migrated"
    return MigrateResult(
        success=True,
        message=f"{action} database ‘{db_config.db_name}’ ({db_config.type})",
    )
