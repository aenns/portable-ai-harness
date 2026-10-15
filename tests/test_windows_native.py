"""Must run on Windows itself; native tests are not replaced by Linux mocks."""

import ctypes
import os
import subprocess
import sys
import time

import pytest

from portable_ai_harness.core import reports
from portable_ai_harness.core.setup import SetupError, prepare_init, read_data, write_init

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Requires native Windows APIs")


def test_job_assignment_failure_does_not_run_project_code(tmp_path, monkeypatch):
    from portable_ai_harness.core.windows import Job

    marker = tmp_path / "never-ran"
    job = Job()
    monkeypatch.setattr(job.kernel, "AssignProcessToJobObject", lambda *args: False)
    try:
        with pytest.raises(OSError):
            job.launch(
                [sys.executable, "-c", f'open({str(marker)!r},"w").write("bad")'],
                cwd=tmp_path,
                env=os.environ.copy(),
            )
    finally:
        job.close()
    time.sleep(0.1)
    assert not marker.exists()


def test_job_kills_descendant_even_in_new_process_group(tmp_path):
    from portable_ai_harness.core.windows import Job

    marker = tmp_path / "late-write"
    child = f'import time;time.sleep(1);open({str(marker)!r},"w").write("bad")'
    parent = (
        'import subprocess,sys;subprocess.Popen([sys.executable,"-c",'
        + repr(child)
        + "],creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,"
        "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)"
    )
    job = Job()
    process = job.launch([sys.executable, "-c", parent], cwd=tmp_path, env=os.environ.copy())
    try:
        process.wait(timeout=10)
        assert process.returncode == 0
        assert job.stop(process)
        time.sleep(1.2)
        assert not marker.exists()
    finally:
        job.close()
        process.stdout.close()
        process.stderr.close()


def test_report_rejects_junction_without_reading_target(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".ai").mkdir()
    junction = tmp_path / ".ai/local"
    # cmd is explicitly used by this native filesystem test only, not task execution.
    subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
        check=True,
        capture_output=True,
    )
    try:
        with pytest.raises(SetupError):
            reports.prepare_store(tmp_path)
        assert not list(outside.iterdir())
    finally:
        junction.rmdir()


def test_pinned_directory_blocks_replacement(tmp_path):
    from portable_ai_harness.core.windows import pinned_directory

    with pinned_directory(tmp_path, (".ai",), create=True) as directory:
        with pytest.raises(OSError):
            os.rename(directory, tmp_path / "moved")


def test_windows_init_race_preserves_existing_manifest(tmp_path):
    proposal = prepare_init(tmp_path)
    (tmp_path / ".ai").mkdir()
    manifest = tmp_path / ".ai/project.json"
    manifest.write_text("preserve me")
    with pytest.raises(SetupError):
        write_init(proposal)
    assert manifest.read_text() == "preserve me"
    assert not list(manifest.parent.glob(".pah-init-*.tmp"))


def test_windows_read_rejects_hardlinked_metadata(tmp_path):
    target = tmp_path / "outside.json"
    target.write_text("{}")
    os.link(target, tmp_path / "team.json")
    with pytest.raises(SetupError):
        read_data(tmp_path, "team.json")


def test_created_report_has_protected_current_user_dacl(tmp_path):
    from ctypes import wintypes as w

    run_id = reports.save_report(tmp_path, {"report_schema": 1, "status": "PASS"})
    path = tmp_path / ".ai/local/reports" / (run_id + ".json")
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    advapi.GetNamedSecurityInfoW.argtypes = [
        w.LPWSTR,
        ctypes.c_int,
        w.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi.GetNamedSecurityInfoW.restype = w.DWORD
    advapi.GetSecurityDescriptorControl.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(w.WORD),
        ctypes.POINTER(w.DWORD),
    ]
    advapi.GetSecurityDescriptorControl.restype = w.BOOL
    descriptor = ctypes.c_void_p()
    assert (
        advapi.GetNamedSecurityInfoW(
            str(path), 1, 4, None, None, None, None, ctypes.byref(descriptor)
        )
        == 0
    )
    try:
        control = w.WORD()
        revision = w.DWORD()
        assert advapi.GetSecurityDescriptorControl(
            descriptor, ctypes.byref(control), ctypes.byref(revision)
        )
        assert control.value & 0x1000  # SE_DACL_PROTECTED: not inherited broad access.
        assert control.value & 0x4  # SE_DACL_PRESENT: no null DACL.
    finally:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        kernel.LocalFree(descriptor)
