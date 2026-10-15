"""Shared portability contracts: paths, task interpreters and Windows pipe capture."""

import os
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from portable_ai_harness.core import execution
from portable_ai_harness.core.config import relative_path
from portable_ai_harness.core.setup import SetupError


@pytest.mark.parametrize(
    "path",
    [
        "src/file.py:stream",
        "NUL",
        "con.txt",
        "work/AUX",
        "COM1.log",
        "dir/trailing.",
        "dir/trailing ",
        "dir/a?b",
    ],
)
def test_windows_unsafe_names_are_rejected_on_every_os(path):
    with pytest.raises(ValueError):
        relative_path(path)


def test_portable_forward_slash_paths_remain_valid():
    assert relative_path("src/core/main.py") == "src/core/main.py"
    assert relative_path(".") == "."


def test_windows_batch_shim_does_not_implicitly_enable_shell(tmp_path):
    plan = SimpleNamespace(executable=str(tmp_path / "tool.cmd"), argv=("tool", "&echo bad"))
    with pytest.raises(SetupError, match="explicit interpreter"):
        execution.windows_argv(plan)


def test_windows_standard_npm_shim_is_explicit_node_script(tmp_path, monkeypatch):
    script = tmp_path / "node_modules/npm/bin/npm-cli.js"
    script.parent.mkdir(parents=True)
    script.write_text("// fixture")
    monkeypatch.setattr(execution.shutil, "which", lambda command: str(tmp_path / "node.exe"))
    plan = SimpleNamespace(executable=str(tmp_path / "npm.cmd"), argv=("npm", "run", "test"))
    assert execution.windows_argv(plan) == [str(tmp_path / "node.exe"), str(script), "run", "test"]


@pytest.mark.parametrize(
    "code,limit,reason,count",
    [
        ("import os;os.write(1,b'a'*512);os.write(2,b'b'*512)", 1024, "EXIT_ZERO", 1024),
        ("import os;os.write(1,b'x'*1000000)", 1024, "OUTPUT_LIMIT", 1024),
        ("import time;time.sleep(30)", 1024, "TIMEOUT", 0),
    ],
)
def test_threaded_pipe_capture_is_bounded_on_every_os(code, limit, reason, count):
    process = subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
    )
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    plan = SimpleNamespace(timeout_seconds=1, max_output_bytes=limit)
    readers = []
    try:
        actual, size, readers = execution._windows_capture(process, plan, buffers, time.monotonic())
        assert actual == reason and size == count
        assert sum(map(len, buffers.values())) <= limit
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
        for reader in readers:
            reader.join(timeout=1)
            assert not reader.is_alive()
        process.stdout.close()
        process.stderr.close()


def test_reject_relative_cwd_with_drive_or_traversal():
    for path in ["C:work", "C:/work", "../work", "//server/share"]:
        with pytest.raises(ValueError):
            relative_path(path)


def test_doctor_reports_this_execution_platform(tmp_path):
    from portable_ai_harness.core.config import ProjectConfig

    (tmp_path / ".ai").mkdir()
    (tmp_path / ".ai/project.json").write_text(ProjectConfig(project="fixture").model_dump_json())
    assert execution.doctor(tmp_path)["execution_platform_supported"] == (
        os.name in {"nt", "posix"}
    )


def test_windows_line_endings_are_normalized_before_control_filtering():
    assert execution._redact("first\r\nsecond\r\n", {}) == "first\nsecond\n"
    assert execution._redact("untrusted\x1b[31m", {}) == "untrusted?[31m"


def test_windows_directory_handle_requests_read_access_and_denies_delete_sharing(
    tmp_path, monkeypatch
):
    from portable_ai_harness.core import windows

    calls = []
    closed = []

    class Kernel:
        def CreateFileW(self, *args):
            calls.append(args)
            return 42

        def GetFileInformationByHandle(self, handle, information):
            information._obj.attributes = 0x10
            return True

        def CloseHandle(self, handle):
            closed.append(handle)
            return True

    kernel = Kernel()
    monkeypatch.setattr(windows, "api", lambda: kernel)
    handle = windows.open_handle(tmp_path, directory=True)
    try:
        assert handle == 42
        _, access, sharing, _, disposition, flags, _ = calls[0]
        assert access == 0x80000000  # GENERIC_READ; metadata-only access is insufficient.
        assert sharing == 3  # FILE_SHARE_READ | FILE_SHARE_WRITE; no FILE_SHARE_DELETE.
        assert disposition == 3  # OPEN_EXISTING.
        assert flags & 0x02000000 and flags & 0x00200000
    finally:
        kernel.CloseHandle(handle)
    assert closed == [42]
