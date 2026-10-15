"""Real short-lived subprocesses verify execution boundaries and failure evidence."""

import json
import os
import subprocess
import sys
import time
from dataclasses import replace

import pytest
from pydantic import ValidationError

from portable_ai_harness.core.config import ProjectConfig
from portable_ai_harness.core.execution import (
    check_plans,
    doctor,
    execute,
    execute_checks,
    execution_exit,
    plan_task,
    report_data,
)
from portable_ai_harness.core.setup import SetupError


def configure(root, tasks, required=None, optional=None):
    (root / ".ai").mkdir(exist_ok=True)
    config = ProjectConfig(
        project="fixture",
        tasks=tasks,
        check_policy={"required": required or [], "optional": optional or []},
    )
    (root / ".ai/project.json").write_text(config.model_dump_json(indent=2))


def python_task(code, **kwargs):
    return {"argv": [sys.executable, "-c", code], **kwargs}


def test_doctor_does_not_execute_project_code_or_dump_environment(tmp_path, monkeypatch):
    configure(
        tmp_path, {"test": python_task("raise RuntimeError('never execute')")}, ["test"], ["absent"]
    )

    def prohibited(*args, **kwargs):
        raise AssertionError("doctor executed a subprocess")

    monkeypatch.setattr(subprocess, "Popen", prohibited)
    result = doctor(tmp_path)
    assert result["required_executables_available"]
    assert result["tasks"][0]["status"] == "AVAILABLE"
    assert result["tasks"][1]["status"] == "NOT_CONFIGURED"
    assert not (tmp_path / ".ai/local").exists()


def test_doctor_reports_missing_required_executable(tmp_path):
    configure(tmp_path, {"test": {"argv": ["pah-absent-executable-fixture"]}}, ["test"])
    result = doctor(tmp_path)
    assert not result["required_executables_available"]
    assert result["tasks"][0]["status"] == "UNAVAILABLE"


def test_plan_does_not_execute_or_create_reports(tmp_path):
    marker = tmp_path / "marker"
    configure(tmp_path, {"test": python_task(f"open({str(marker)!r},'w').write('bad')")})
    plan = plan_task(tmp_path, "test")
    assert plan.preview()["argv"][1] == "-c"
    assert not marker.exists()
    assert not (tmp_path / ".ai/local").exists()


def test_execution_preserves_literal_arguments_cwd_and_exit_zero(tmp_path):
    (tmp_path / "work").mkdir()
    code = "import os,sys;print(os.path.basename(os.getcwd()));print(sys.argv[1])"
    configure(
        tmp_path,
        {
            "test": {
                "argv": [sys.executable, "-c", code, "$(touch should-not-exist)"],
                "cwd": "work",
            }
        },
    )
    result = execute(plan_task(tmp_path, "test"))
    assert result.status == "PASS" and result.task_exit_code == 0
    assert result.stdout.splitlines() == ["work", "$(touch should-not-exist)"]
    assert not (tmp_path / "work/should-not-exist").exists()


def test_nonzero_exit_and_stderr_are_reported(tmp_path):
    configure(
        tmp_path, {"test": python_task("import sys;print('failure',file=sys.stderr);sys.exit(7)")}
    )
    result = execute(plan_task(tmp_path, "test"))
    assert result.status == "FAIL" and result.reason == "EXIT_NONZERO"
    assert result.task_exit_code == 7 and "failure" in result.stderr
    assert execution_exit(result) == 1


def test_missing_executable_is_not_passing(tmp_path):
    configure(tmp_path, {"test": {"argv": ["pah-absent-executable-fixture"]}})
    result = execute(plan_task(tmp_path, "test"))
    assert result.reason == "EXECUTABLE_UNAVAILABLE"
    assert result.task_exit_code is None
    assert execution_exit(result) == 4


def test_timeout_is_bounded_and_not_success(tmp_path):
    configure(tmp_path, {"test": python_task("import time;time.sleep(30)", timeout_seconds=1)})
    start = time.monotonic()
    result = execute(plan_task(tmp_path, "test"))
    assert time.monotonic() - start < 4
    assert result.status == "FAIL" and result.reason == "TIMEOUT"
    assert result.task_exit_code is not None


def test_output_limit_stops_a_flood_without_unbounded_capture(tmp_path):
    configure(
        tmp_path, {"test": python_task("import os;os.write(1,b'x'*1000000)", max_output_bytes=1024)}
    )
    result = execute(plan_task(tmp_path, "test"))
    assert result.reason == "OUTPUT_LIMIT" and result.status == "FAIL"
    assert result.output_bytes == 1024
    assert len(result.stdout.encode()) + len(result.stderr.encode()) <= 1024


def test_exact_limit_and_both_pipes_can_pass(tmp_path):
    configure(
        tmp_path,
        {
            "test": python_task(
                "import os;os.write(1,b'a'*512);os.write(2,b'b'*512)", max_output_bytes=1024
            )
        },
    )
    result = execute(plan_task(tmp_path, "test"))
    assert result.status == "PASS"
    assert result.stdout == "a" * 512 and result.stderr == "b" * 512


def test_changed_manifest_invalidates_the_reviewed_plan(tmp_path):
    configure(tmp_path, {"test": python_task("print('old')")})
    plan = plan_task(tmp_path, "test")
    configure(tmp_path, {"test": python_task("print('new')")})
    with pytest.raises(SetupError, match="changed after approval"):
        execute(plan)


def test_forged_plan_cannot_change_argv(tmp_path):
    configure(tmp_path, {"test": python_task("print('allowed')")})
    plan = replace(plan_task(tmp_path, "test"), argv=(sys.executable, "-c", "print('forged')"))
    with pytest.raises(SetupError, match="changed after approval"):
        execute(plan)


def test_new_cwd_symlink_is_denied_before_execution(tmp_path):
    cwd = tmp_path / "work"
    cwd.mkdir()
    configure(tmp_path, {"test": python_task("print('never')", cwd="work")})
    plan = plan_task(tmp_path, "test")
    cwd.rmdir()
    cwd.symlink_to(tmp_path)
    with pytest.raises(SetupError):
        execute(plan)


def test_services_cannot_use_short_task_runner(tmp_path):
    configure(
        tmp_path,
        {"dev": python_task("print('never')", side_effect="local-service", lifecycle="service")},
    )
    with pytest.raises(SetupError, match="lifecycle"):
        plan_task(tmp_path, "dev")


def test_environment_requires_explicit_allowlist_and_known_secrets_are_masked(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("PAH_TEST_SECRET_TOKEN", "secret-value-for-test")
    code = "import os;print(os.environ.get('PAH_TEST_SECRET_TOKEN','absent'))"
    configure(tmp_path, {"test": python_task(code)})
    assert execute(plan_task(tmp_path, "test")).stdout.strip() == "absent"
    configure(tmp_path, {"test": python_task(code, env_allow=["PAH_TEST_SECRET_TOKEN"])})
    result = execute(plan_task(tmp_path, "test"))
    assert "secret-value-for-test" not in result.stdout
    assert "[REDACTED]" in result.stdout
    assert "stdout" not in result.evidence()


def test_check_required_failure_skips_following_work(tmp_path):
    marker = tmp_path / "must-not-exist"
    configure(
        tmp_path,
        {
            "bad": python_task("raise SystemExit(7)"),
            "later": python_task(f"open({str(marker)!r},'w').write('bad')"),
        },
        ["bad", "later"],
        ["optional"],
    )
    plans, required, fingerprint = check_plans(tmp_path)
    results, passed = execute_checks(tmp_path, plans, required, fingerprint)
    assert not passed
    assert [r.status for r in results] == ["FAIL", "SKIPPED", "SKIPPED"]
    assert not marker.exists()


def test_optional_failures_and_absences_remain_explicit(tmp_path):
    configure(
        tmp_path,
        {"ok": python_task("print('ok')"), "advisory": python_task("exit(8)")},
        ["ok"],
        ["advisory", "absent"],
    )
    plans, required, fingerprint = check_plans(tmp_path)
    results, passed = execute_checks(tmp_path, plans, required, fingerprint)
    assert passed
    assert [r.status for r in results] == ["PASS", "FAIL", "NOT_CONFIGURED"]
    data = report_data("check", "fixture", fingerprint, results, passed, required)
    assert data["required_tasks"] == ["ok"]
    assert "argv" not in json.dumps(data) or "Raw output/argv" in data["note"]
    assert all("stdout" not in row and "stderr" not in row for row in data["tasks"])


def test_empty_required_checks_are_not_a_pass(tmp_path):
    configure(tmp_path, {})
    assert not doctor(tmp_path)["required_checks_configured"]
    with pytest.raises(SetupError, match="NOT_CONFIGURED"):
        check_plans(tmp_path)


def test_duplicate_checks_are_rejected():
    with pytest.raises(ValidationError):
        ProjectConfig(
            project="example",
            tasks={"test": python_task("pass")},
            check_policy={"required": ["test", "test"]},
        )


def test_parent_exit_does_not_leave_ordinary_background_child(tmp_path):
    marker = tmp_path / "late-child-write"
    child = f"import time;time.sleep(0.5);open({str(marker)!r},'w').write('bad')"
    code = (
        "import subprocess,sys;subprocess.Popen([sys.executable,'-c',"
        + repr(child)
        + "],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)"
    )
    configure(tmp_path, {"test": python_task(code)})
    result = execute(plan_task(tmp_path, "test"))
    assert result.status == "PASS"
    time.sleep(0.7)
    assert not marker.exists()


def test_timeout_cleans_up_ordinary_child_process_group(tmp_path):
    marker = tmp_path / "late-child-write"
    child = f"import time;time.sleep(1.5);open({str(marker)!r},'w').write('bad')"
    code = (
        "import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',"
        + repr(child)
        + "]);time.sleep(30)"
    )
    configure(tmp_path, {"test": python_task(code, timeout_seconds=1)})
    assert execute(plan_task(tmp_path, "test")).reason == "TIMEOUT"
    time.sleep(0.7)
    assert not marker.exists()


def test_keyboard_interrupt_is_a_failed_cancelled_result(tmp_path, monkeypatch):
    import portable_ai_harness.core.execution as module

    configure(tmp_path, {"test": python_task("import time;time.sleep(30)")})
    if os.name == "nt":
        original_capture = module._windows_capture

        def interrupted_capture(process, plan, buffers, start):
            # Expired deadline ensures reader creation/cleanup, then simulate cancel.
            _, count, readers = original_capture(process, plan, buffers, start - 10000)
            return "CANCELLED", count, readers

        monkeypatch.setattr(module, "_windows_capture", interrupted_capture)
        result = execute(plan_task(tmp_path, "test"))
        assert result.reason == "CANCELLED" and execution_exit(result) == 130
        assert result.cleanup_confirmed is True
        return
    original = module.selectors.DefaultSelector

    class InterruptSelector(original):
        def select(self, timeout=None):
            raise KeyboardInterrupt

    monkeypatch.setattr(module.selectors, "DefaultSelector", InterruptSelector)
    result = execute(plan_task(tmp_path, "test"))
    assert result.reason == "CANCELLED" and execution_exit(result) == 130


@pytest.mark.parametrize(
    "settings",
    [
        {"max_output_bytes": 0},
        {"max_output_bytes": 1048577},
        {"env_allow": ["BAD-NAME"]},
    ],
)
def test_execution_settings_are_bounded(settings):
    with pytest.raises(ValidationError):
        ProjectConfig(project="example", tasks={"test": python_task("pass", **settings)})
