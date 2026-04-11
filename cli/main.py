# cli/main.py
import typer
import shutil
from pathlib import Path

app = typer.Typer(help="Ana Offline Administrative CLI")
config_app = typer.Typer(help="Manage Ana's configuration files")
app.add_typer(config_app, name="config")

STORAGE_DIR = Path("storage/local_repo")
CONFIG_DIR = Path("config")

@app.command("init")
def init_system():
    """Bootstrap the local environment."""
    typer.echo("Initializing Ana system...")
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    typer.echo(f"Ensured local storage directory exists at {STORAGE_DIR}")
    typer.echo("TODO: Execute EdgeDB initial schema migrations.")

@app.command("reset")
def reset_system(force: bool = typer.Option(False, "--force", "-f", help="Force reset without prompting")):
    """Safely truncate the EdgeDB graph and clear the local file repository."""
    if not force:
        confirm = typer.confirm("This will delete all data in the local repository and EdgeDB. Are you sure?")
        if not confirm:
            typer.echo("Reset cancelled.")
            raise typer.Abort()

    typer.echo("Resetting system...")
    if STORAGE_DIR.exists():
        shutil.rmtree(STORAGE_DIR)
        STORAGE_DIR.mkdir()
    typer.echo("Cleared local file repository.")
    typer.echo("TODO: Execute EdgeDB truncation.")

@app.command("backup")
def backup_system():
    """Dump the EdgeDB schema/data and archive the local file repository."""
    typer.echo("Starting system backup...")
    # Example archiving logic
    archive_path = shutil.make_archive("ana_storage_backup", 'gztar', STORAGE_DIR)
    typer.echo(f"Backed up local storage to {archive_path}")
    typer.echo("TODO: Execute EdgeDB schema and data dump.")

@config_app.command("generate")
def config_generate():
    """Scaffold default YAML configuration files."""
    CONFIG_DIR.mkdir(exist_ok=True)
    default_config = CONFIG_DIR / "scheduler.yml"
    if not default_config.exists():
        with open(default_config, "w") as f:
            f.write("# Ana Rocketry Schedule Configuration\n")
            f.write("tasks:\n  - name: fetch_daily_data\n    cron: '0 0 * * *'\n")
        typer.echo(f"Generated default config at {default_config}")
    else:
        typer.echo(f"Config already exists at {default_config}")

@config_app.command("update")
def config_update():
    """Validate and apply updates to existing YAML configurations."""
    typer.echo("Validating configuration files...")
    typer.echo("TODO: Load YAML, validate against Pydantic models, and apply.")

if __name__ == "__main__":
    app()
