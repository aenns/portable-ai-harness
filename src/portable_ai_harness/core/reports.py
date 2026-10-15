"""Private bounded local outcome reports, with no-follow directory-relative access."""

import json
import os
import re
import stat
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from portable_ai_harness.core.setup import SetupError

ID_PATTERN = re.compile(r"^[0-9]{8}T[0-9]{12}Z-[a-f0-9]{32}$")
MAX_REPORT_BYTES = 262144
MAX_REPORTS = 100


def _directory(root: Path, create: bool) -> int:
    if os.name != "posix":
        raise SetupError("Local report storage currently requires macOS/Linux", 4)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(root, flags)
    try:
        for part in [".ai", "local", "reports"]:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except OSError as exc:
        os.close(fd)
        raise SetupError(
            "Report directory missing or unsafe; inspect .ai/local/reports", 3
        ) from exc


def prepare_store(root: Path) -> None:
    if os.name == "nt":
        from portable_ai_harness.core.windows import pinned_directory

        try:
            with pinned_directory(root, (".ai", "local", "reports"), create=True) as directory:
                if len(_names(directory)) >= MAX_REPORTS:
                    raise SetupError(
                        "Report capacity reached; review/remove older local reports", 3
                    )
        except OSError as exc:
            raise SetupError("Report directory missing or unsafe", 3) from exc
        return
    fd = _directory(root, True)
    try:
        if len(_names(fd)) >= MAX_REPORTS:
            raise SetupError("Report capacity reached; review/remove older local reports", 3)
    finally:
        os.close(fd)


def _names(fd: int) -> list[str]:
    names = []
    with os.scandir(fd) as entries:
        for count, entry in enumerate(entries):
            if count >= 2000:
                raise SetupError("Report directory exceeds inspection bound; clean up manually", 3)
            if entry.name.endswith(".json") and ID_PATTERN.fullmatch(entry.name[:-5]):
                names.append(entry.name)
    return sorted(names)


def save_report(root: Path, report: dict) -> str:
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex
    report = {**report, "run_id": run_id}
    content = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode()
    if len(content) > MAX_REPORT_BYTES:
        raise SetupError("Report exceeds storage bound; no raw output was retained", 3)
    if os.name == "nt":
        return _windows_save(root, run_id, content)
    fd = _directory(root, True)
    temporary = f".report-{uuid4().hex}.tmp"
    try:
        if len(_names(fd)) >= MAX_REPORTS:
            raise SetupError("Report capacity reached; task side effects are not rolled back", 3)
        file_fd = os.open(
            temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd
        )
        try:
            with os.fdopen(file_fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(
                temporary, run_id + ".json", src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False
            )
        finally:
            os.unlink(temporary, dir_fd=fd)
    except OSError as exc:
        raise SetupError(
            "Could not store report; task side effects are not rolled back", 3
        ) from exc
    finally:
        os.close(fd)
    return run_id


def read_report(root: Path, run_id: str | None = None) -> dict:
    if run_id is not None and not ID_PATTERN.fullmatch(run_id):
        raise SetupError("Invalid report ID", 3)
    if os.name == "nt":
        return _windows_read(root, run_id)
    fd = _directory(root, False)
    try:
        names = _names(fd)
        if run_id is None:
            if not names:
                raise SetupError("No saved reports available")
            name = names[-1]
        else:
            name = run_id + ".json"
        file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        if not stat.S_ISREG(os.fstat(file_fd).st_mode):
            os.close(file_fd)
            raise SetupError("Report must be a regular file", 3)
        with os.fdopen(file_fd, "rb") as stream:
            content = stream.read(MAX_REPORT_BYTES + 1)
        if len(content) > MAX_REPORT_BYTES:
            raise SetupError("Report exceeds read bound", 3)
        value = json.loads(content)
        if not isinstance(value, dict) or value.get("report_schema") != 1:
            raise SetupError("Unsupported report data")
        return value
    except (OSError, ValueError, RecursionError) as exc:
        raise SetupError("Report missing, invalid or unsafe", 3) from exc
    finally:
        os.close(fd)


def _windows_save(root, run_id, content):
    from portable_ai_harness.core.windows import open_stream, pinned_directory

    try:
        with pinned_directory(root, (".ai", "local", "reports"), create=True) as directory:
            if len(_names(directory)) >= MAX_REPORTS:
                raise SetupError(
                    "Report capacity reached; task side effects are not rolled back", 3
                )
            temporary = directory / f".report-{uuid4().hex}.tmp"
            try:
                with open_stream(temporary, create=True) as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.rename(temporary, directory / (run_id + ".json"))
            finally:
                temporary.unlink(missing_ok=True)
    except OSError as exc:
        raise SetupError(
            "Could not store report; task side effects are not rolled back", 3
        ) from exc
    return run_id


def _windows_read(root, run_id):
    from portable_ai_harness.core.windows import open_stream, pinned_directory

    try:
        with pinned_directory(root, (".ai", "local", "reports")) as directory:
            names = _names(directory)
            if run_id is None and not names:
                raise SetupError("No saved reports available")
            name = run_id + ".json" if run_id is not None else names[-1]
            with open_stream(directory / name) as stream:
                content = stream.read(MAX_REPORT_BYTES + 1)
        if len(content) > MAX_REPORT_BYTES:
            raise SetupError("Report exceeds read bound", 3)
        value = json.loads(content)
        if not isinstance(value, dict) or value.get("report_schema") != 1:
            raise SetupError("Unsupported report data")
        return value
    except (OSError, ValueError, RecursionError) as exc:
        raise SetupError("Report missing, invalid or unsafe", 3) from exc
