"""User-facing setup preserves files unless an explicit create is confirmed."""

import json

from typer.testing import CliRunner

from portable_ai_harness.cli import app

runner = CliRunner()


def test_dry_run_never_creates_ai_directory(tmp_path):
    result = runner.invoke(app, ["init", "--root", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert '"schema_version": 1' in result.stdout
    assert "DRY RUN" in result.stdout
    assert not (tmp_path / ".ai").exists()


def test_declined_confirmation_leaves_no_files(tmp_path):
    result = runner.invoke(app, ["init", "--root", str(tmp_path)], input="n\n")
    assert result.exit_code == 1
    assert not (tmp_path / ".ai").exists()


def test_eof_does_not_authorize_creation(tmp_path):
    result = runner.invoke(app, ["init", "--root", str(tmp_path)], input="")
    assert result.exit_code != 0
    assert not (tmp_path / ".ai").exists()


def test_confirmation_writes_exact_preview(tmp_path):
    result = runner.invoke(
        app, ["init", "--root", str(tmp_path), "--project", "my-project"], input="y\n"
    )
    assert result.exit_code == 0, result.output
    path = tmp_path / ".ai/project.json"
    assert json.loads(path.read_text())["project"] == "my-project"
    assert "No tasks were executed" in result.stdout


def test_explicit_cli_yes_and_validate(tmp_path):
    result = runner.invoke(app, ["init", "--root", str(tmp_path), "--yes"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["config", "validate", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "VALID: schema 1" in result.stdout
    assert "readiness" in result.stdout


def test_existing_config_is_preserved_without_confirmation(tmp_path):
    runner.invoke(app, ["init", "--root", str(tmp_path), "--yes"])
    path = tmp_path / ".ai/project.json"
    before = path.read_bytes()
    result = runner.invoke(app, ["init", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "preserved" in result.stdout
    assert "Create this" not in result.stdout
    assert path.read_bytes() == before


def test_unsupported_profile_is_actionable(tmp_path):
    result = runner.invoke(
        app, ["init", "--root", str(tmp_path), "--profile", "terraform", "--yes"]
    )
    assert result.exit_code == 2
    assert "python and node" in result.output
    assert not (tmp_path / ".ai").exists()


def test_explicit_profile_is_not_a_claim_of_installed_toolchain(tmp_path):
    result = runner.invoke(app, ["init", "--root", str(tmp_path), "--profile", "python", "--yes"])
    assert result.exit_code == 0
    data = json.loads((tmp_path / ".ai/project.json").read_text())
    assert data["profiles"] == ["python"]
    assert data["tasks"] == {}


def test_schema_output_is_json_not_terminal_help():
    result = runner.invoke(app, ["config", "schema"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["properties"]["schema_version"]["const"] == 1


def test_validation_error_does_not_echo_secret(tmp_path):
    (tmp_path / ".ai").mkdir()
    (tmp_path / ".ai/project.json").write_text('{"project":"p","password":"SUPER_PRIVATE"}')
    result = runner.invoke(app, ["config", "validate", "--root", str(tmp_path)])
    assert result.exit_code == 2
    assert "SUPER_PRIVATE" not in result.output
    assert "Traceback" not in result.output


def test_denied_template_has_policy_exit_code(tmp_path):
    result = runner.invoke(
        app, ["init", "--root", str(tmp_path), "--config-template", "../other.json"]
    )
    assert result.exit_code == 3
    assert not (tmp_path / ".ai").exists()


def test_validation_of_missing_config_is_clear(tmp_path):
    result = runner.invoke(app, ["config", "validate", "--root", str(tmp_path)])
    assert result.exit_code == 2
    assert "missing" in result.output
