# src/cli.py
import typer
import subprocess
import shutil
import yaml
import datetime
from pathlib import Path
from pydantic import BaseModel, ValidationError
import gel

app = typer.Typer(help="Ana Offline Administrative CLI")
config_app = typer.Typer(help="Manage Ana's configuration files")
app.add_typer(config_app, name="config")

# --- Global Configuration Paths ---
STORAGE_DIR = Path("local_storage") # Ensure this matches LocalResourceRepository base_dir
CONFIG_DIR = Path("config")

# --- Pydantic Models for Config Validation ---
class TaskConfig(BaseModel):
    name: str
    cron: str

class SchedulerConfig(BaseModel):
    tasks: list[TaskConfig]


@app.command("init")
def init():
    """Initialize the Gel database and run migrations."""
    typer.echo("Initializing Gel project...")

    # Ensure local storage exists
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Ensured local storage directory exists at {STORAGE_DIR}")

    try:
        # Run the gel init command non-interactively
        subprocess.run(["gel", "project", "init", "--non-interactive"], check=True)
        typer.echo("Running database migrations...")
        subprocess.run(["gel", "migrate"], check=True)
        typer.secho("✅ Initialization complete.", fg=typer.colors.GREEN)
    except subprocess.CalledProcessError as e:
        typer.secho(f"❌ Initialization failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command("reset")
def reset(force: bool = typer.Option(False, "--force", "-f", help="Force reset without confirmation")):
    """Wipe local storage and truncate the Gel knowledge graph."""
    if not force:
        confirm = typer.confirm("This will delete all data in the local repository and Gel Graph. Are you sure?")
        if not confirm:
            typer.echo("Aborted.")
            raise typer.Exit()

    # 1. Wipe the local resource storage
    typer.echo("Wiping local resource storage...")
    if STORAGE_DIR.exists():
        shutil.rmtree(STORAGE_DIR)
        STORAGE_DIR.mkdir()
        typer.echo("Local storage wiped.")

    # 2. Truncate the Gel Knowledge Graph
    typer.echo("Truncating Knowledge Graph...")
    try:
        client = gel.create_client()
        # Delete all tuples from the graph
        client.query("delete SPOCTuple;")
        typer.echo("Knowledge Graph truncated.")
        typer.secho("✅ System reset complete.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"❌ Database reset failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command("backup")
def backup(output_dir: str = typer.Option("backups", help="Directory to save the backups")):
    """Backup the Gel database and local storage to a zip and dump file."""
    out_path = Path(output_dir)
    out_path.mkdir(exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. Zip local storage
    typer.echo("Backing up local storage...")
    archive_name = out_path / f"ana_storage_backup_{timestamp}"
    if STORAGE_DIR.exists():
        shutil.make_archive(str(archive_name), 'zip', STORAGE_DIR)
        typer.echo(f"Storage backup saved to {archive_name}.zip")
    else:
        typer.echo("No local storage found to backup.")

    # 2. Dump Gel database
    typer.echo("Dumping Knowledge Graph...")
    dump_file = out_path / f"ana_graph_dump_{timestamp}.dmp"
    try:
        subprocess.run(["gel", "dump", str(dump_file)], check=True)
        typer.echo(f"Knowledge Graph dumped to {dump_file}")
        typer.secho("✅ Backup complete.", fg=typer.colors.GREEN)
    except subprocess.CalledProcessError as e:
        typer.secho(f"❌ Database dump failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@config_app.command("generate")
def config_generate():
    """Scaffold default YAML configuration files."""
    CONFIG_DIR.mkdir(exist_ok=True)
    default_config = CONFIG_DIR / "scheduler.yaml"
    if not default_config.exists():
        with open(default_config, "w") as f:
            f.write("# Ana Schedule Configuration\n")
            f.write("actions:\n  - name: fetch_daily_data\n    cron: '0 0 * * *'\n")
        typer.echo(f"Generated default config at {default_config}")
    else:
        typer.echo(f"Config already exists at {default_config}")


@config_app.command("validate")
def config_validate(file_path: str = typer.Option("config/scheduler.yml", help="Path to scheduler config")):
    """Validate and format the scheduler configuration file."""
    path = Path(file_path)
    if not path.exists():
        typer.secho(f"❌ Config file not found at {file_path}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    try:
        with open(path, "r") as f:
            raw_data = yaml.safe_load(f)

        # Validate against the strictly typed Pydantic model
        validated_config = SchedulerConfig(**raw_data)

        # Write it back perfectly formatted
        with open(path, "w") as f:
            yaml.dump(validated_config.model_dump(), f, default_flow_style=False, sort_keys=False)

        typer.secho(f"✅ Configuration at {file_path} is valid and has been formatted.", fg=typer.colors.GREEN)
    except ValidationError as e:
        typer.secho(f"❌ Configuration validation failed:\n{e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
