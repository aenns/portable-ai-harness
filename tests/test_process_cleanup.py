"""Platform-neutral regressions for denied signaling and cleanup-state decisions."""

import os
import signal

import pytest

from portable_ai_harness.core import execution
from portable_ai_harness.core.config import ProjectConfig


@pytest.mark.parametrize(
    "data,expected",
    [
        (b"1 S\n42 Z\n", True),
        (b"42 Z+\n", True),
        (b"42 Z\n42 S\n", False),
        (b"1 R\n", True),
        (b"42 R\n", False),
        (b"", True),
        (b"unexpected-format\n", None),
        (b"42 \xff\n", None),
    ],
)
def test_group_state_must_distinguish_zombies_live_and_unknown(data, expected):
    assert execution._parse_group_state(data, 42) is expected


class ExitedProcess:
    pid = 42
    returncode = 0

    def poll(self):
        return 0

    def wait(self, timeout=None):
        return 0


@pytest.mark.skipif(os.name == "nt", reason="POSIX signaling backend only")
def test_no_kill_is_sent_after_group_disappears(monkeypatch):
    calls = []

    def killpg(pid, sig):
        calls.append(sig)
        if sig == 0:
            raise ProcessLookupError

    monkeypatch.setattr(execution.os, "killpg", killpg)
    assert execution._stop_group(ExitedProcess()) is True
    assert signal.SIGKILL not in calls


@pytest.mark.skipif(os.name == "nt", reason="POSIX signaling backend only")
@pytest.mark.parametrize("state,expected", [(True, True), (False, False), (None, False)])
def test_permission_error_requires_verified_group_state(monkeypatch, state, expected):
    monkeypatch.setattr(execution, "CLEANUP_GRACE_SECONDS", 0)

    def killpg(pid, sig):
        if sig == signal.SIGKILL:
            raise PermissionError

    monkeypatch.setattr(execution.os, "killpg", killpg)
    monkeypatch.setattr(execution, "_group_quiescent", lambda group: state)
    assert execution._stop_group(ExitedProcess()) is expected


def test_unconfirmed_cleanup_cannot_be_a_successful_task(tmp_path, monkeypatch):
    import sys

    (tmp_path / ".ai").mkdir()
    config = ProjectConfig(
        project="fixture", tasks={"test": {"argv": [sys.executable, "-c", "print('done')"]}}
    )
    (tmp_path / ".ai/project.json").write_text(config.model_dump_json())
    if os.name == "nt":
        from portable_ai_harness.core.windows import Job

        original = Job.stop

        def stop_but_unconfirmed(self, process):
            original(self, process)
            return False

        monkeypatch.setattr(Job, "stop", stop_but_unconfirmed)
    else:
        monkeypatch.setattr(execution, "_stop_group", lambda process: False)
    result = execution.execute(execution.plan_task(tmp_path, "test"))
    assert result.status == "FAIL" and result.reason == "CLEANUP_UNCONFIRMED"
    assert result.cleanup_confirmed is False
    assert result.task_exit_code == 0
