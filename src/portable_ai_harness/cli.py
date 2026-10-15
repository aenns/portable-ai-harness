"""Terminal adapter: parsing/rendering only; core services contain application behavior."""

import json
from dataclasses import asdict
from typing import Annotated

import typer

from portable_ai_harness.core.version import VersionInfo, get_version_info

app = typer.Typer(
    help="Portable AI Harness — reusable development tools. Step 04A provides version/help only.",
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
