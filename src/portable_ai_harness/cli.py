"""Terminal adapter: parsing/rendering only; core services contain application behavior."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from portable_ai_harness.core.config import ProjectConfig
from portable_ai_harness.core.setup import SetupError, load_config, prepare_init, write_init
from portable_ai_harness.core.version import VersionInfo, get_version_info

app = typer.Typer(
    help=(
        "Portable AI Harness — reusable development tools. "
        "Safe project initialization and configuration validation."
    ),
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version_info() -> VersionInfo:
    try:
        return get_version_info()
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"Portable AI Harness {_version_info().cli_version}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", callback=_show_version, is_eager=True, help="Show CLI version."),
    ] = False,
) -> None:
    """Show help when invoked without a subcommand; do not discover or edit a project."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command("version")
def version_report(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit a machine-readable version report.")
    ] = False,
) -> None:
    """Report installed package/runtime identity without contacting a provider."""
    info = _version_info()
    if json_output:
        typer.echo(json.dumps({"report_schema": 1, **asdict(info)}, sort_keys=True))
    else:
        typer.echo(f"Portable AI Harness {info.cli_version}")
        typer.echo(f"Python {info.python_version}")


@app.command("init")
def initialize(
    root: Annotated[
        Path, typer.Option(exists=True, file_okay=False, help="Selected project root.")
    ] = Path("."),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without writing.")] = False,
    profile: Annotated[
        list[str] | None,
        typer.Option("--profile", help="Explicit python/node profiles; repeatable."),
    ] = None,
    project: Annotated[str | None, typer.Option(help="Override project identity.")] = None,
    config_template: Annotated[
        str | None, typer.Option(help="Workspace-relative local JSON template.")
    ] = None,
    yes: Annotated[
        bool, typer.Option("--yes", help="Explicit CLI consent to create the previewed manifest.")
    ] = False,
) -> None:
    """Discover and preview configuration; create only after explicit CLI confirmation."""
    try:
        if profile and any(item not in {"python", "node"} for item in profile):
            raise SetupError(
                "Unsupported profile. Tested definitions are python and node; "
                "use explicit tasks for other toolchains."
            )
        proposal = prepare_init(root, profiles=profile, project=project, template=config_template)
        for note in proposal.notes:
            typer.echo(note)
        typer.echo(proposal.text)
        if proposal.existing:
            return
        if dry_run:
            typer.echo("DRY RUN: would create .ai/project.json; no files written.")
            return
        if not yes and not typer.confirm("Create this .ai/project.json?", default=False):
            typer.echo("Cancelled; no files written.")
            raise typer.Exit(code=1)
        write_init(proposal)
        typer.echo("Created .ai/project.json. No tasks were executed.")
    except SetupError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.code) from exc
    except OSError as exc:
        typer.echo("Cannot access the selected workspace safely.", err=True)
        raise typer.Exit(code=3) from exc


config_app = typer.Typer(
    help="Validate project configuration or print generated structural schema."
)
app.add_typer(config_app, name="config")


@config_app.command("validate")
def validate_configuration(
    root: Annotated[Path, typer.Option(exists=True, file_okay=False)] = Path("."),
) -> None:
    """Validate data, references and configured paths; does not execute tasks or probe providers."""
    try:
        config = load_config(root.resolve(strict=True))
        typer.echo(f"VALID: schema {config.schema_version}, project {config.project}")
        typer.echo("Configuration only; task readiness and model/MCP support are not implied.")
    except SetupError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.code) from exc
    except OSError as exc:
        typer.echo("Cannot access configuration safely.", err=True)
        raise typer.Exit(code=3) from exc


@config_app.command("schema")
def configuration_schema() -> None:
    """Print structural JSON Schema; the core additionally enforces cross-field/path rules."""
    typer.echo(json.dumps(ProjectConfig.model_json_schema(), indent=2, sort_keys=True))
