"""Real filesystem fixtures exercise discovery, precedence, create-only writes and races."""

import json
import os

import pytest

from portable_ai_harness.core.setup import (
    CONFIG_PATH,
    SetupError,
    load_config,
    prepare_init,
    read_data,
    write_init,
)


def python_project(root):
    (root / "pyproject.toml").write_text("""[project]
name = "fixture"
dependencies = []
[dependency-groups]
dev = ["pytest>=8", "ruff>=0.12"]
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
""")
    (root / "uv.lock").write_text("fixture only; never executed")


def test_unknown_project_preview_is_read_only(tmp_path):
    before = list(tmp_path.iterdir())
    proposal = prepare_init(tmp_path)
    data = json.loads(proposal.text)
    assert data["profiles"] == [] and data["tasks"] == {}
    assert data["check_policy"]["required"] == []
    assert list(tmp_path.iterdir()) == before
    assert not proposal.existing


def test_python_uv_discovery_uses_declared_tools(tmp_path):
    python_project(tmp_path)
    data = json.loads(prepare_init(tmp_path).text)
    assert data["profiles"] == ["python"]
    assert data["tasks"]["test"]["argv"] == ["uv", "run", "--locked", "pytest"]
    assert data["tasks"]["lint"]["argv"][-3:] == ["ruff", "check", "."]
    assert data["tasks"]["build"]["side_effect"] == "local-build"


def test_python_without_uv_does_not_invent_tasks(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="example"\n')
    assert json.loads(prepare_init(tmp_path).text)["tasks"] == {}


def test_node_scripts_are_data_and_no_flags_are_invented(tmp_path):
    sentinel = tmp_path / "SHOULD_NOT_EXIST"
    (tmp_path / "package.json").write_text(
        json.dumps(
            {"scripts": {"test": f"touch {sentinel}", "build": "build-tool", "dev": "server"}}
        )
    )
    data = json.loads(prepare_init(tmp_path).text)
    assert data["profiles"] == ["node"]
    assert data["tasks"]["test"]["argv"] == ["npm", "run", "test"]
    assert data["tasks"]["dev"]["lifecycle"] == "service"
    assert "dev" not in data["check_policy"]["required"]
    assert not sentinel.exists()


def test_template_and_explicit_values_override_discovery(tmp_path):
    python_project(tmp_path)
    (tmp_path / "team.json").write_text(
        json.dumps(
            {
                "project": "team",
                "profiles": ["node"],
                "tasks": {"test": {"argv": ["custom", "test"]}},
                "documentation": {"mode": "off"},
            }
        )
    )
    data = json.loads(
        prepare_init(tmp_path, profiles=["python"], project="explicit", template="team.json").text
    )
    assert data["project"] == "explicit" and data["profiles"] == ["python"]
    assert data["documentation"]["mode"] == "off"
    assert data["tasks"]["test"]["argv"] == ["custom", "test"]
    assert data["tasks"]["test"]["timeout_seconds"] == 120


def test_mixed_project_conflict_requires_a_template_choice(tmp_path):
    python_project(tmp_path)
    (tmp_path / "package.json").write_text('{"scripts":{"test":"node-test"}}')
    with pytest.raises(SetupError, match="conflict"):
        prepare_init(tmp_path)
    (tmp_path / "team.json").write_text('{"tasks":{"test":{"argv":["reviewed-test"]}}}')
    config = json.loads(prepare_init(tmp_path, template="team.json").text)
    assert config["profiles"] == ["python", "node"]
    assert config["tasks"]["test"]["argv"] == ["reviewed-test"]


def test_write_and_rerun_preserve_original_bytes(tmp_path):
    proposal = prepare_init(tmp_path)
    assert write_init(proposal)
    path = tmp_path / CONFIG_PATH
    original = path.read_bytes()
    (tmp_path / "package.json").write_text('{"scripts":{"test":"new-test"}}')
    again = prepare_init(tmp_path, project="different")
    assert again.existing
    assert not write_init(again)
    assert path.read_bytes() == original
    assert load_config(tmp_path).project != "different"
    assert not list((tmp_path / ".ai").glob("*.tmp"))


def test_intervening_file_is_not_replaced(tmp_path):
    proposal = prepare_init(tmp_path)
    (tmp_path / ".ai").mkdir()
    path = tmp_path / CONFIG_PATH
    path.write_text("preserve another writer")
    with pytest.raises(SetupError, match="not replaced"):
        write_init(proposal)
    assert path.read_text() == "preserve another writer"
    assert not list((tmp_path / ".ai").glob("*.tmp"))


@pytest.mark.parametrize("target", [".ai", "package.json", "team.json"])
def test_symlink_read_or_write_paths_are_denied(tmp_path, target):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.json").write_text('{"private":"keep"}')
    (tmp_path / target).symlink_to(outside if target == ".ai" else outside / "secret.json")
    with pytest.raises(SetupError) as caught:
        prepare_init(tmp_path, template="team.json" if target == "team.json" else None)
    assert caught.value.code == 3
    assert not (outside / "project.json").exists()


def test_symlink_inserted_after_preview_is_denied(tmp_path):
    proposal = prepare_init(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".ai").symlink_to(outside)
    with pytest.raises(SetupError):
        write_init(proposal)
    assert list(outside.iterdir()) == []


def test_oversized_metadata_is_rejected(tmp_path):
    (tmp_path / "package.json").write_bytes(b" " * 128001)
    with pytest.raises(SetupError, match="limit"):
        prepare_init(tmp_path)


def test_denied_template_is_not_read(tmp_path):
    (tmp_path / ".env").write_text("SECRET=private")
    with pytest.raises(SetupError) as caught:
        prepare_init(tmp_path, template=".env")
    assert caught.value.code == 3


@pytest.mark.parametrize("data", ["[project]\nname = ", '[project]\ndependencies="bad"'])
def test_malformed_python_metadata_fails_cleanly(tmp_path, data):
    (tmp_path / "pyproject.toml").write_text(data)
    with pytest.raises(SetupError):
        prepare_init(tmp_path)


def test_bad_existing_config_is_not_overwritten(tmp_path):
    (tmp_path / ".ai").mkdir()
    path = tmp_path / CONFIG_PATH
    path.write_text('{"schema_version":99}')
    with pytest.raises(SetupError):
        prepare_init(tmp_path)
    assert path.read_text() == '{"schema_version":99}'


def test_task_cwd_escape_and_symlink_are_denied(tmp_path):
    (tmp_path / "link").symlink_to(tmp_path)
    (tmp_path / "team.json").write_text('{"tasks":{"test":{"argv":["x"],"cwd":"link"}}}')
    with pytest.raises(SetupError) as caught:
        prepare_init(tmp_path, template="team.json")
    assert caught.value.code == 3


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO fixture requires os.mkfifo")
def test_no_fifo_read_hang(tmp_path):
    os.mkfifo(tmp_path / "package.json")
    with pytest.raises(SetupError, match="regular file"):
        read_data(tmp_path, "package.json")


def test_ambiguous_package_manager_requires_reviewed_tasks(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts":{"test":"node-test"}}')
    (tmp_path / "yarn.lock").write_text("fixture")
    with pytest.raises(SetupError, match="resolve tasks"):
        prepare_init(tmp_path)
    (tmp_path / "team.json").write_text('{"tasks":{"test":{"argv":["yarn","test"]}}}')
    proposal = prepare_init(tmp_path, template="team.json")
    assert json.loads(proposal.text)["tasks"]["test"]["argv"] == ["yarn", "test"]


def test_metadata_directory_rejected_as_nonregular(tmp_path):
    (tmp_path / "package.json").mkdir()
    with pytest.raises(SetupError):
        prepare_init(tmp_path)


def test_unsupported_node_manager_does_not_invent_npm(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"packageManager":"bun@1.0.0","scripts":{"test":"bun test"}}'
    )
    with pytest.raises(SetupError, match="resolve tasks"):
        prepare_init(tmp_path)
