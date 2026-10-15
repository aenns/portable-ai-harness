"""Reports are private bounded outcome files, never a reason to execute a task."""

import os

import pytest

from portable_ai_harness.core import reports
from portable_ai_harness.core.setup import SetupError


def example():
    return {"report_schema": 1, "kind": "run", "status": "PASS", "tasks": []}


def test_report_roundtrip_and_latest(tmp_path):
    reports.prepare_store(tmp_path)
    first = reports.save_report(tmp_path, example())
    second = reports.save_report(tmp_path, {**example(), "status": "FAIL"})
    assert reports.read_report(tmp_path, first)["status"] == "PASS"
    assert reports.read_report(tmp_path)["run_id"] == second
    assert reports.read_report(tmp_path, second)["status"] == "FAIL"
    path = tmp_path / ".ai/local/reports" / (second + ".json")
    if os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600
    # Windows permissions are DACLs; native-only tests verify the protected ACL.


def test_report_storage_rejects_symlink_directory(tmp_path):
    (tmp_path / ".ai").mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".ai/local").symlink_to(outside)
    with pytest.raises(SetupError):
        reports.prepare_store(tmp_path)
    assert list(outside.iterdir()) == []


def test_report_id_cannot_escape(tmp_path):
    with pytest.raises(SetupError, match="Invalid report ID"):
        reports.read_report(tmp_path, "../../secret")


def test_report_file_symlink_is_not_followed(tmp_path):
    run_id = reports.save_report(tmp_path, example())
    path = tmp_path / ".ai/local/reports" / (run_id + ".json")
    outside = tmp_path / "outside.json"
    outside.write_text('{"private":"keep"}')
    path.unlink()
    path.symlink_to(outside)
    with pytest.raises(SetupError):
        reports.read_report(tmp_path, run_id)
    assert outside.read_text() == '{"private":"keep"}'


def test_report_capacity_does_not_delete_existing_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(reports, "MAX_REPORTS", 2)
    first = reports.save_report(tmp_path, example())
    second = reports.save_report(tmp_path, example())
    with pytest.raises(SetupError, match="capacity"):
        reports.prepare_store(tmp_path)
    with pytest.raises(SetupError, match="capacity"):
        reports.save_report(tmp_path, example())
    assert reports.read_report(tmp_path, first)
    assert reports.read_report(tmp_path, second)


def test_oversized_report_not_stored(tmp_path):
    with pytest.raises(SetupError, match="bound"):
        reports.save_report(tmp_path, {**example(), "extra": "x" * 262145})
    assert not (tmp_path / ".ai/local").exists()


def test_tampered_report_read_is_bounded(tmp_path):
    run_id = reports.save_report(tmp_path, example())
    path = tmp_path / ".ai/local/reports" / (run_id + ".json")
    path.write_bytes(b"x" * 262145)
    with pytest.raises(SetupError, match="bound"):
        reports.read_report(tmp_path, run_id)
