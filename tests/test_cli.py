"""CLI behavior, parse errors and machine-readable output using the installed package."""

import json
from importlib import metadata

import pytest
from typer.testing import CliRunner

from portable_ai_harness import cli
from portable_ai_harness.core.version import VersionInfo

runner = CliRunner()


@pytest.mark.parametrize("args", [[], ["--help"], ["-h"]])
def test_help_lists_only_implemented_commands(args):
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 0
    assert "version" in result.stdout
    assert "Safe project" in result.stdout
    assert "init" in result.stdout
    assert "config" in result.stdout


def test_version_option_uses_installed_metadata():
    result = runner.invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == f"Portable AI Harness {metadata.version('portable-ai-harness')}"


def test_version_command_uses_shared_core(monkeypatch):
    monkeypatch.setattr(cli, "get_version_info", lambda: VersionInfo("example", "9.8.7", "3.12.15"))
    result = runner.invoke(cli.app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.splitlines() == ["Portable AI Harness 9.8.7", "Python 3.12.15"]


def test_json_is_parseable_and_reports_actual_installed_identity():
    result = runner.invoke(cli.app, ["version", "--json"])
    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["report_schema"] == 1
    assert report["distribution"] == "portable-ai-harness"
    assert report["cli_version"] == metadata.version("portable-ai-harness")
    assert report["python_version"].startswith("3.")


@pytest.mark.parametrize("args", [["unknown"], ["--unknown"], ["version", "--unknown"]])
def test_invalid_input_is_a_usage_error(args):
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 2


def test_core_failure_is_reported_without_fake_version(monkeypatch):
    def missing():
        raise RuntimeError("Package metadata is missing")

    monkeypatch.setattr(cli, "get_version_info", missing)
    result = runner.invoke(cli.app, ["--version"])
    assert result.exit_code == 1
    assert "Package metadata is missing" in result.output
    assert "Traceback" not in result.output
