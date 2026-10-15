"""Explicit named task execution with bounded pipes, duration and owned process groups.

This is not an OS sandbox. Reviewed programs retain user privileges and can write
files, use the network or intentionally detach from the process group.
"""

import hashlib
import os
import queue
import re
import selectors
import shutil
import signal
import subprocess
import threading
import time
import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from portable_ai_harness.core.config import Task
from portable_ai_harness.core.setup import SetupError, load_config, read_data, safe_path

BASE_ENV = {
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "TMPDIR",
    "TMP",
    "TEMP",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "NO_COLOR",
    "CI",
    "VIRTUAL_ENV",
    "UV_CACHE_DIR",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "SYSTEMROOT",
    "COMSPEC",
    "WINDIR",
    "PATHEXT",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "PROGRAMDATA",
    "SYSTEMDRIVE",
}


@dataclass(frozen=True)
class TaskPlan:
    root: Path
    config_hash: str
    name: str
    argv: tuple[str, ...]
    cwd: str
    executable: str | None
    timeout_seconds: int
    max_output_bytes: int
    side_effect: str
    env_allow: tuple[str, ...]

    def preview(self) -> dict:
        value = asdict(self)
        value.pop("root")
        value.pop("executable")
        value["executable_available"] = self.executable is not None
        return value


@dataclass(frozen=True)
class TaskResult:
    task: str
    status: str
    reason: str
    task_exit_code: int | None
    duration_seconds: float
    output_bytes: int
    stdout: str = ""
    stderr: str = ""
    cleanup_confirmed: bool | None = None

    def evidence(self) -> dict:
        """Retain outcomes, not arbitrary task text or credential-bearing arguments."""
        value = asdict(self)
        value.pop("stdout")
        value.pop("stderr")
        return value


def _resolve(root: Path, task: Task) -> str | None:
    cwd = safe_path(root, task.cwd)
    executable = task.argv[0]
    if not os.path.isabs(executable) and ("/" in executable or "\\" in executable):
        executable = str(cwd / executable)
    found = shutil.which(executable)
    return str(Path(found).absolute()) if found else None


def manifest_hash(root: Path) -> str:
    return hashlib.sha256(read_data(root, ".ai/project.json")).hexdigest()


def plan_task(root: Path, name: str) -> TaskPlan:
    root = root.resolve(strict=True)
    before = manifest_hash(root)
    config = load_config(root)
    if name not in config.tasks:
        raise SetupError("Named task is not configured")
    task = config.tasks[name]
    if task.lifecycle != "task":
        raise SetupError(
            "Service tasks require the later dev lifecycle workflow; run/check refuse them"
        )
    after = manifest_hash(root)
    if before != after:
        raise SetupError("Configuration changed during preview; review again", 3)
    return TaskPlan(
        root,
        after,
        name,
        tuple(task.argv),
        task.cwd,
        _resolve(root, task),
        task.timeout_seconds,
        task.max_output_bytes,
        task.side_effect,
        tuple(task.env_allow),
    )


def doctor(root: Path) -> dict:
    """Inspect data and executable presence only: no subprocess, hooks, model or network probes."""
    root = root.resolve(strict=True)
    config = load_config(root)
    rows = []
    required = set(config.check_policy.required)
    for name, task in config.tasks.items():
        rows.append(
            {
                "task": name,
                "required": name in required,
                "status": "AVAILABLE" if _resolve(root, task) else "UNAVAILABLE",
                "lifecycle": task.lifecycle,
            }
        )
    for name in config.check_policy.optional:
        if name not in config.tasks:
            rows.append(
                {"task": name, "required": False, "status": "NOT_CONFIGURED", "lifecycle": None}
            )
    return {
        "project": config.project,
        "tasks": rows,
        "required_executables_available": all(
            row["status"] == "AVAILABLE" for row in rows if row["required"]
        ),
        "required_checks_configured": bool(required),
        "execution_platform_supported": os.name in {"posix", "nt"},
        "note": "Presence only; nested tools/versions and task correctness are not verified.",
    }


def check_plans(root: Path) -> tuple[list[TaskPlan], list[str], str]:
    root = root.resolve(strict=True)
    fingerprint = manifest_hash(root)
    config = load_config(root)
    if not config.check_policy.required:
        raise SetupError("Required checks are NOT_CONFIGURED; select a named task with run")
    names = [*config.check_policy.required, *config.check_policy.optional]
    plans = [plan_task(root, name) for name in names if name in config.tasks]
    if fingerprint != manifest_hash(root) or any(p.config_hash != fingerprint for p in plans):
        raise SetupError("Configuration changed during check preview; review again", 3)
    return plans, list(config.check_policy.required), fingerprint


def _environment(plan: TaskPlan) -> dict:
    names = BASE_ENV | set(plan.env_allow)
    return (
        {
            key: value
            for key, value in os.environ.items()
            if key.upper() in {name.upper() for name in names}
        }
        if os.name == "nt"
        else {key: value for key, value in os.environ.items() if key in names}
    )


def _redact(value: str, environment: dict) -> str:
    value = value.replace("\r\n", "\n")
    secrets = [
        text
        for key, text in environment.items()
        if re.search(r"TOKEN|SECRET|PASSWORD|API_KEY|PRIVATE_KEY", key, re.I) and len(text) >= 4
    ]
    for text in sorted(secrets, key=len, reverse=True):
        value = value.replace(text, "[REDACTED]")
    # Do not let child output inject terminal control sequences.
    return "".join(
        ch if ch in "\n\t" or unicodedata.category(ch) not in {"Cc", "Cf"} else "?" for ch in value
    )


CLEANUP_GRACE_SECONDS = 0.2


def _parse_group_state(output: bytes, group_id: int) -> bool | None:
    """True means absent/zombie-only; False means live members; None means unknown."""
    try:
        lines = output.decode("ascii").splitlines()
        live = False
        for line in lines:
            if not line.strip():
                continue
            fields = line.split()
            if (
                len(fields) != 2
                or not fields[0].isdigit()
                or not re.fullmatch(r"[A-Za-z][A-Za-z0-9+<>-]*", fields[1])
            ):
                return None
            if int(fields[0]) == group_id and fields[1][0].upper() not in {"Z", "X"}:
                live = True
        return not live
    except UnicodeError:
        return None


def _group_quiescent(group_id: int) -> bool | None:
    """Bounded OS state fallback after denied signaling; never inspect command args/env."""
    process = None
    selector = selectors.DefaultSelector()
    output = bytearray()
    try:
        process = subprocess.Popen(
            ["/bin/ps", "-axo", "pgid=,state="],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
        os.set_blocking(process.stdout.fileno(), False)
        selector.register(process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + 1
        while selector.get_map() or process.poll() is None:
            if time.monotonic() >= deadline:
                return None
            for key, _ in selector.select(0.02):
                chunk = os.read(key.fileobj.fileno(), 8192)
                if not chunk:
                    selector.unregister(key.fileobj)
                else:
                    output.extend(chunk)
                    if len(output) > 1048576:
                        return None
        if process.returncode != 0:
            return None
        return _parse_group_state(bytes(output), group_id)
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        selector.close()
        if process is not None:
            if process.poll() is None:
                try:
                    process.kill()
                except OSError:
                    pass
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
            process.stdout.close()


def _stop_group(process: subprocess.Popen) -> bool:
    """Allow group-wide TERM grace; verify an EPERM instead of hiding it or crashing."""
    try:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            process.wait(timeout=1)
            return True
        except PermissionError:
            pass  # Escalation/state verification below must still establish cleanup.
        deadline = time.monotonic() + CLEANUP_GRACE_SECONDS
        while time.monotonic() < deadline:
            process.poll()  # Reap the leader; wait alone does not wait for descendants.
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                process.wait(timeout=1)
                return True
            except PermissionError:
                pass
            time.sleep(0.01)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except PermissionError:
            # Darwin may deny signaling a zombie-only group. An errno alone is
            # insufficient: live or unknown state must never be accepted as clean.
            if _group_quiescent(process.pid) is not True:
                return False
        process.wait(timeout=1)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        # A failed group cleanup must not leave the direct child running if it can
        # still be killed. This does not turn failed group cleanup into success.
        if process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=1)
            except (OSError, subprocess.SubprocessError):
                pass


def execute(plan: TaskPlan) -> TaskResult:
    """Execute an already-reviewed plan; callers must own the human approval boundary."""
    if os.name not in {"posix", "nt"}:
        raise SetupError("Execution requires Windows, macOS or Linux", 4)
    if manifest_hash(plan.root) != plan.config_hash:
        raise SetupError("Configuration changed after approval; preview and approve again", 3)
    # Reload path rules and executable resolution immediately before execution.
    current = plan_task(plan.root, plan.name)
    if current != plan:
        raise SetupError("Task or executable changed after approval; preview again", 3)
    if plan.executable is None:
        return TaskResult(plan.name, "FAIL", "EXECUTABLE_UNAVAILABLE", None, 0, 0)
    environment = _environment(plan)
    start = time.monotonic()
    job = None
    try:
        if os.name == "nt":
            from portable_ai_harness.core.windows import Job

            argv = windows_argv(plan)
            job = Job()
            process = job.launch(argv, cwd=safe_path(plan.root, plan.cwd), env=environment)
        else:
            process = subprocess.Popen(
                [plan.executable, *plan.argv[1:]],
                cwd=safe_path(plan.root, plan.cwd),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=True,
            )
    except OSError:
        if job is not None:
            job.close()
        return TaskResult(plan.name, "FAIL", "PROCESS_START_FAILED", None, 0, 0)
    reason = "EXIT_ZERO"
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    count = 0
    selector = selectors.DefaultSelector() if os.name != "nt" else None
    readers = []
    try:
        if os.name == "nt":
            reason, count, readers = _windows_capture(process, plan, buffers, start)
        else:
            reason, count = _posix_capture(process, plan, buffers, start, selector)
    except KeyboardInterrupt:
        reason = "CANCELLED"
    finally:
        if selector is not None:
            selector.close()
        cleanup_confirmed = job.stop(process) if job is not None else _stop_group(process)
        for reader in readers:
            reader.join(timeout=1)
        process.stdout.close()
        process.stderr.close()
    if not cleanup_confirmed:
        reason = "CLEANUP_UNCONFIRMED"
    if reason == "EXIT_ZERO" and process.returncode != 0:
        reason = "EXIT_NONZERO"
    return TaskResult(
        plan.name,
        "PASS" if reason == "EXIT_ZERO" else "FAIL",
        reason,
        process.returncode,
        round(time.monotonic() - start, 3),
        count,
        _redact(buffers["stdout"].decode("utf-8", errors="replace"), environment),
        _redact(buffers["stderr"].decode("utf-8", errors="replace"), environment),
        cleanup_confirmed,
    )


def _posix_capture(process, plan, buffers, start, selector):
    reason = "EXIT_ZERO"
    count = 0
    try:
        for stream, name in [(process.stdout, "stdout"), (process.stderr, "stderr")]:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map() or process.poll() is None:
            remaining = plan.timeout_seconds - (time.monotonic() - start)
            if remaining <= 0:
                reason = "TIMEOUT"
                break
            events = selector.select(min(0.05, remaining))
            for key, _ in events:
                try:
                    chunk = os.read(key.fileobj.fileno(), 8192)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                room = plan.max_output_bytes - count
                retained = chunk[:room]
                buffers[key.data].extend(retained)
                count += len(retained)
                if len(chunk) > room:
                    reason = "OUTPUT_LIMIT"
                    break
            if reason != "EXIT_ZERO":
                break
    except KeyboardInterrupt:
        reason = "CANCELLED"
    return reason, count


def windows_argv(plan):
    """Do not implicitly interpret .cmd/.bat arguments in cmd.exe.

    Standard Node npm installs have an adjacent npm-cli.js: invoke that through
    node.exe directly. Other scripts need an explicitly configured interpreter.
    """
    executable = Path(plan.executable)
    if executable.suffix.lower() not in {".cmd", ".bat"}:
        return [str(executable), *plan.argv[1:]]
    npm_cli = executable.parent / "node_modules/npm/bin/npm-cli.js"
    node = shutil.which("node")
    if executable.name.lower() == "npm.cmd" and npm_cli.is_file() and node:
        return [node, str(npm_cli), *plan.argv[1:]]
    raise SetupError(
        "Windows batch shims require an explicit interpreter in task argv; "
        "use node plus the package manager JS entry point (standard npm is adapted)",
        4,
    )


def _windows_capture(process, plan, buffers, start):
    """Windows pipes are not selectable. Two readers feed a bounded shared queue."""
    chunks = queue.Queue(maxsize=8)
    stop = threading.Event()
    readers = []

    def pump(stream, name):
        try:
            while not stop.is_set():
                chunk = os.read(stream.fileno(), 8192)
                while not stop.is_set():
                    try:
                        chunks.put((name, chunk), timeout=0.05)
                        break
                    except queue.Full:
                        continue
                if not chunk:
                    return
        except (OSError, ValueError):
            while not stop.is_set():
                try:
                    chunks.put((name, None), timeout=0.05)
                    return
                except queue.Full:
                    continue

    for stream, name in [(process.stdout, "stdout"), (process.stderr, "stderr")]:
        thread = threading.Thread(target=pump, args=(stream, name), daemon=True)
        readers.append(thread)
        thread.start()
    reason = "EXIT_ZERO"
    count = 0
    ended = set()
    try:
        while len(ended) < 2 or process.poll() is None:
            if time.monotonic() - start >= plan.timeout_seconds:
                reason = "TIMEOUT"
                break
            try:
                name, chunk = chunks.get(timeout=0.02)
            except queue.Empty:
                continue
            if chunk is None:
                reason = "OUTPUT_READ_FAILED"
                break
            if not chunk:
                ended.add(name)
                continue
            room = plan.max_output_bytes - count
            buffers[name].extend(chunk[:room])
            count += min(len(chunk), room)
            if len(chunk) > room:
                reason = "OUTPUT_LIMIT"
                break
    except KeyboardInterrupt:
        reason = "CANCELLED"
    finally:
        stop.set()
    return reason, count, readers


def execute_checks(
    root: Path, plans: list[TaskPlan], required: list[str], fingerprint: str, progress=None
) -> tuple[list[TaskResult], bool]:
    """Fail fast after a required failure, retaining explicit skipped/absent outcomes."""
    config = load_config(root)
    if manifest_hash(root) != fingerprint:
        raise SetupError("Check configuration changed after approval", 3)
    expected = [
        name
        for name in [*config.check_policy.required, *config.check_policy.optional]
        if name in config.tasks
    ]
    if required != config.check_policy.required or [p.name for p in plans] != expected:
        raise SetupError("Check selection differs from the reviewed configuration", 3)
    plan_map = {plan.name: plan for plan in plans}
    results = []
    failed = False
    for name in [*config.check_policy.required, *config.check_policy.optional]:
        if failed:
            results.append(TaskResult(name, "SKIPPED", "PRIOR_REQUIRED_FAILURE", None, 0, 0))
            continue
        if name not in plan_map:
            results.append(TaskResult(name, "NOT_CONFIGURED", "OPTIONAL_TASK_ABSENT", None, 0, 0))
            continue
        if progress:
            progress(name)
        try:
            result = execute(plan_map[name])
        except SetupError as exc:
            result = TaskResult(name, "FAIL", f"POLICY_OR_CONFIGURATION_{exc.code}", None, 0, 0)
        results.append(result)
        if (
            result.status != "PASS"
            and name in required
            or result.reason == "CANCELLED"
            or result.reason.startswith("POLICY_OR_CONFIGURATION")
        ):
            failed = True
    return results, not failed


def execution_exit(result: TaskResult) -> int:
    if result.reason == "CANCELLED":
        return 130
    if result.reason == "EXECUTABLE_UNAVAILABLE":
        return 4
    return 0 if result.status == "PASS" else 1


def report_data(
    kind: str,
    project: str,
    fingerprint: str,
    results: list[TaskResult],
    passed: bool,
    required: list[str] | None = None,
) -> dict:
    from portable_ai_harness.core.version import get_version_info

    return {
        "report_schema": 1,
        "kind": kind,
        "project": project,
        "status": "PASS" if passed else "FAIL",
        "config_sha256": fingerprint,
        "harness_version": get_version_info().cli_version,
        "recorded_at": datetime.now(UTC).isoformat(),
        "required_tasks": required or [],
        "tasks": [result.evidence() for result in results],
        "note": "Observed task outcomes, not feature acceptance. Raw output/argv are not stored.",
    }
