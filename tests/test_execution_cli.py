"""Terminal approval, preview, real execution and reporting integration."""

import json
import sys

from typer.testing import CliRunner

from portable_ai_harness.cli import app
from portable_ai_harness.core.config import ProjectConfig

runner = CliRunner()


def setup(root, *, missing=False):
    (root / ".ai").mkdir()
    task = (
        {"argv": ["pah-absent-executable-fixture"]}
        if missing
        else {"argv": [sys.executable, "-c", "print('fixture success')"]}
    )
    config = ProjectConfig(
        project="fixture", tasks={"test": task}, check_policy={"required": ["test"]}
    )
    (root / ".ai/project.json").write_text(config.model_dump_json(indent=2))


def test_doctor_json_contains_readiness_not_a_test_pass(tmp_path):
    setup(tmp_path)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["tasks"][0]["status"] == "AVAILABLE"
    assert "not verified" in data["note"]
    assert not (tmp_path / ".ai/local").exists()


def test_doctor_missing_required_executable_exits_four(tmp_path):
    setup(tmp_path, missing=True)
    result = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert result.exit_code == 4
    assert "UNAVAILABLE" in result.stdout


def test_run_preview_is_read_only(tmp_path):
    setup(tmp_path)
    result = runner.invoke(app, ["run", "test", "--root", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN" in result.stdout and 'fixture success\\"' not in result.stdout
    assert not (tmp_path / ".ai/local").exists()


def test_check_preview_is_read_only(tmp_path):
    setup(tmp_path)
    result = runner.invoke(app, ["check", "--root", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0
    assert '"required"' in result.stdout and "DRY RUN" in result.stdout
    assert not (tmp_path / ".ai/local").exists()


def test_declined_execution_writes_no_report(tmp_path):
    setup(tmp_path)
    result = runner.invoke(app, ["run", "test", "--root", str(tmp_path)], input="n\n")
    assert result.exit_code == 1
    assert not (tmp_path / ".ai/local").exists()


def test_eof_does_not_authorize_a_task(tmp_path):
    setup(tmp_path)
    result = runner.invoke(app, ["check", "--root", str(tmp_path)], input="")
    assert result.exit_code != 0
    assert not (tmp_path / ".ai/local").exists()


def test_confirmed_run_saves_outcomes_without_raw_output(tmp_path):
    setup(tmp_path)
    result = runner.invoke(app, ["run", "test", "--root", str(tmp_path)], input="y\n")
    assert result.exit_code == 0, result.output
    assert "test: PASS" in result.stdout and "Report ID:" in result.stdout
    paths = list((tmp_path / ".ai/local/reports").glob("*.json"))
    assert len(paths) == 1
    data = json.loads(paths[0].read_text())
    assert data["tasks"][0]["task_exit_code"] == 0
    assert "stdout" not in data["tasks"][0]
    assert "fixture success" not in paths[0].read_text()


def test_check_and_report_do_not_confuse_stored_outcomes_with_reexecution(tmp_path):
    setup(tmp_path)
    result = runner.invoke(app, ["check", "--root", str(tmp_path), "--yes"])
    assert result.exit_code == 0, result.output
    assert "Required checks: PASS" in result.stdout
    before = list((tmp_path / ".ai/local/reports").glob("*.json"))
    result = runner.invoke(app, ["report", "--root", str(tmp_path)])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["kind"] == "check" and data["required_tasks"] == ["test"]
    assert list((tmp_path / ".ai/local/reports").glob("*.json")) == before


def test_missing_run_task_is_not_success(tmp_path):
    setup(tmp_path)
    result = runner.invoke(app, ["run", "unknown", "--root", str(tmp_path), "--yes"])
    assert result.exit_code == 2
    assert "not configured" in result.output


def test_report_path_escape_is_denied(tmp_path):
    setup(tmp_path)
    result = runner.invoke(app, ["report", "../secret", "--root", str(tmp_path)])
    assert result.exit_code == 3


def test_missing_executable_run_records_failure(tmp_path):
    setup(tmp_path, missing=True)
    result = runner.invoke(app, ["run", "test", "--root", str(tmp_path), "--yes"])
    assert result.exit_code == 4
    assert "EXECUTABLE_UNAVAILABLE" in result.stdout
    report = next((tmp_path / ".ai/local/reports").glob("*.json"))
    assert json.loads(report.read_text())["status"] == "FAIL"
