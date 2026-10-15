"""Bounded metadata discovery, configuration validation and create-only initialization.

POSIX directory-relative writes pin the destination and never replace an existing file.
This protects init's own operations, not arbitrary third-party programs or the whole OS.
"""

import json
import os
import re
import shutil
import stat
import tomllib
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from portable_ai_harness.core.config import ProjectConfig, relative_path

MAX_METADATA_BYTES = 128000
CONFIG_PATH = ".ai/project.json"


class SetupError(Exception):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def safe_path(root: Path, relative: str) -> Path:
    try:
        relative_path(relative)
    except ValueError as exc:
        raise SetupError(
            "Path denied: use an allowed path within the selected workspace", 3
        ) from exc
    path = root
    for part in Path(relative).parts:
        path = path / part
        if path.is_symlink():
            raise SetupError("Symlink paths are denied during configuration/setup", 3)
    if not path.resolve().is_relative_to(root):
        raise SetupError("Path escapes the selected workspace", 3)
    return path


def read_data(root: Path, relative: str, *, optional: bool = False) -> bytes | None:
    path = safe_path(root, relative)
    try:
        # Final-component no-follow plus ancestor checks; no metadata is executed/imported.
        fd = os.open(
            path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        )
    except FileNotFoundError:
        if optional:
            return None
        raise SetupError("Required configuration/metadata file is missing") from None
    except OSError as exc:
        raise SetupError("Cannot open configuration/metadata safely", 3) from exc
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise SetupError("Configuration/metadata must be a regular file", 3)
    with os.fdopen(fd, "rb") as stream:
        data = stream.read(MAX_METADATA_BYTES + 1)
    if len(data) > MAX_METADATA_BYTES:
        raise SetupError("Configuration/metadata exceeds the 128000-byte limit", 3)
    return data


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SetupError("Duplicate JSON object keys are not allowed")
        result[key] = value
    return result


def parse_json(data: bytes) -> dict:
    try:
        result = json.loads(data, object_pairs_hook=_unique_pairs)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise SetupError("Invalid JSON data; input contents are not echoed") from exc
    if not isinstance(result, dict):
        raise SetupError("Expected a JSON object")
    return result


def validate(root: Path, value: dict) -> ProjectConfig:
    try:
        config = ProjectConfig.model_validate(value)
    except ValidationError as exc:
        # Error locations/field names may themselves contain secrets; print only error codes.
        kinds = sorted(
            {error["type"] for error in exc.errors(include_input=False, include_url=False)}
        )
        raise SetupError(
            "Invalid project configuration ("
            + ", ".join(kinds)
            + "); check schema/field names, types, profiles, paths and references"
        ) from exc
    for task in config.tasks.values():
        if not safe_path(root, task.cwd).is_dir():
            raise SetupError("A task cwd must be an existing workspace directory", 3)
    for instruction in config.instructions.paths:
        if not safe_path(root, instruction).is_file():
            raise SetupError("Instruction paths must name existing workspace files", 3)
    for output in [config.documentation.feature_output, config.documentation.changelog]:
        safe_path(root, output)
    return config


def load_config(root: Path) -> ProjectConfig:
    return validate(root, parse_json(read_data(root, CONFIG_PATH)))


def merge(lower: dict, higher: dict) -> dict:
    """Maps merge recursively, lists replace, task entries replace as whole definitions."""
    result = dict(lower)
    for key, value in higher.items():
        if key == "tasks" and isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = {**result[key], **value}
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def discover(root: Path, overrides: set[str]) -> tuple[dict, list[str]]:
    result = {"profiles": [], "tasks": {}}
    notes = []
    python_data = read_data(root, "pyproject.toml", optional=True)
    if python_data is not None:
        try:
            py = tomllib.loads(python_data.decode("utf-8"))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise SetupError("Invalid pyproject.toml; metadata was not executed") from exc
        if any(
            not isinstance(py.get(key, {}), dict)
            for key in ["project", "tool", "dependency-groups"]
        ):
            raise SetupError("Invalid Python metadata table structure")
        if not isinstance(py.get("project", {}).get("dependencies", []), list):
            raise SetupError("Python dependencies must be a list")
        result["profiles"].append("python")
        uv = safe_path(root, "uv.lock").is_file() or "uv" in py.get("tool", {})
        if uv:
            groups = py.get("dependency-groups", {})
            dependencies = [*py.get("project", {}).get("dependencies", [])]
            for group in groups.values():
                if isinstance(group, list):
                    dependencies.extend(item for item in group if isinstance(item, str))
            names = {
                re.split(r"[\[<>=!~;\s]", item, maxsplit=1)[0].lower()
                for item in dependencies
                if isinstance(item, str)
            }
            for name, command in [("lint", ["ruff", "check", "."]), ("test", ["pytest"])]:
                if command[0] in names:
                    result["tasks"][name] = {"argv": ["uv", "run", "--locked", *command]}
            if "build-system" in py:
                result["tasks"]["build"] = {"argv": ["uv", "build"], "side_effect": "local-build"}
            notes.append(
                "Python/uv task proposals use declared dependencies; review selected groups."
            )
        else:
            notes.append("Python metadata found without uv evidence; configure tasks explicitly.")
    node_data = read_data(root, "package.json", optional=True)
    if node_data is not None:
        node = parse_json(node_data)
        result["profiles"].append("node")
        manager_field = node.get("packageManager", "")
        if not isinstance(manager_field, str):
            raise SetupError("packageManager must be a string")
        manager = manager_field.split("@")[0] if manager_field else "npm"
        if not manager_field and any(
            safe_path(root, name).exists() for name in ["pnpm-lock.yaml", "yarn.lock"]
        ):
            manager = "unresolved"
        scripts = node.get("scripts", {})
        if not isinstance(scripts, dict) or any(not isinstance(v, str) for v in scripts.values()):
            raise SetupError("package.json scripts must be a string map")
        if manager in {"npm", "pnpm", "yarn"}:
            for name in ["lint", "types", "test", "build", "dev"]:
                if name in scripts and scripts[name].strip():
                    task = {"argv": [manager, "run", name]}
                    if name == "build":
                        task["side_effect"] = "local-build"
                    if name == "dev":
                        task.update(side_effect="local-service", lifecycle="service")
                    if name in result["tasks"]:
                        if name not in overrides:
                            raise SetupError(
                                "Python/Node task name conflict; "
                                "choose task definitions in a template"
                            )
                        notes.append("Template resolves a Python/Node task name conflict.")
                    result["tasks"][name] = task
            notes.append(
                "Node tasks use actual scripts without invented runner flags; review watch modes."
            )
        else:
            needed = {name for name in scripts if name in {"lint", "types", "test", "build", "dev"}}
            if needed - overrides:
                raise SetupError(
                    "Package manager unresolved/unsupported; resolve tasks in a template"
                )
            notes.append("Template supplies reviewed tasks for the unresolved package manager.")
    for name, hint in [("pom.xml", "Maven"), ("main.tf", "Terraform")]:
        path = safe_path(root, name)
        if path.exists():
            notes.append(f"{hint} metadata hint only; no automatic tasks/profile support yet.")
    result["check_policy"] = {
        "required": [
            name for name, task in result["tasks"].items() if task.get("lifecycle") != "service"
        ]
    }
    return result, notes


@dataclass(frozen=True)
class InitProposal:
    root: Path
    text: str
    existing: bool
    notes: tuple[str, ...]


def prepare_init(
    root: Path,
    *,
    profiles: list[str] | None = None,
    project: str | None = None,
    template: str | None = None,
) -> InitProposal:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise SetupError("Selected root must be a directory", 3)
    path = safe_path(root, CONFIG_PATH)
    if path.exists():
        config = load_config(root)
        return InitProposal(
            root,
            config.model_dump_json(indent=2) + "\n",
            True,
            ("Existing manifest validated and preserved; init does not update it.",),
        )
    template_data = parse_json(read_data(root, template)) if template is not None else {}
    overrides = template_data.get("tasks", {})
    if not isinstance(overrides, dict):
        raise SetupError("Template tasks must be a JSON object")
    discovered, notes = discover(root, set(overrides))
    slug = re.sub(r"[^A-Za-z0-9_.-]", "-", root.name)[:128] or "project"
    value = merge(ProjectConfig(project=slug).model_dump(), discovered)
    value = merge(value, template_data)
    if profiles is not None:
        value["profiles"] = profiles
    if project is not None:
        value["project"] = project
    config = validate(root, value)
    for task in config.tasks.values():
        if shutil.which(task.argv[0]) is None:
            notes.append(
                "A proposed task executable is missing; doctor/check will fail until installed."
            )
            break
    notes.append(
        "Only project.json is created; "
        "packs, lockfile, task execution, models and MCP follow later."
    )
    return InitProposal(root, config.model_dump_json(indent=2) + "\n", False, tuple(notes))


def write_init(proposal: InitProposal) -> bool:
    """Create reviewed bytes after CLI confirmation; MCP approval is future work."""
    if proposal.existing:
        return False
    if os.name != "posix":
        raise SetupError(
            "Safe init writes currently require macOS/Linux; preview remains available", 4
        )
    validate(proposal.root, parse_json(proposal.text.encode("utf-8")))
    safe_path(proposal.root, CONFIG_PATH)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    root_fd = os.open(proposal.root, flags)
    try:
        try:
            os.mkdir(".ai", mode=0o755, dir_fd=root_fd)
        except FileExistsError:
            pass
        ai_fd = os.open(".ai", flags, dir_fd=root_fd)
        try:
            temporary = f".pah-init-{uuid4().hex}.tmp"
            fd = os.open(
                temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=ai_fd
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    stream.write(proposal.text)
                    stream.flush()
                    os.fsync(stream.fileno())
                # Link fully written bytes to a new destination: never replace an existing file.
                os.link(
                    temporary,
                    "project.json",
                    src_dir_fd=ai_fd,
                    dst_dir_fd=ai_fd,
                    follow_symlinks=False,
                )
            finally:
                os.unlink(temporary, dir_fd=ai_fd)
        finally:
            os.close(ai_fd)
    except OSError as exc:
        raise SetupError(
            "Configuration was not replaced; inspect .ai and rerun preview", 3
        ) from exc
    finally:
        os.close(root_fd)
    return True
