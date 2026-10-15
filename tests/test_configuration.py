"""Versioned data and cross-field invariants, with a generated structural schema."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from portable_ai_harness.core.config import ProjectConfig, relative_path
from portable_ai_harness.core.setup import SetupError, merge, parse_json, validate


def test_defaults_are_offline_and_conservative():
    config = ProjectConfig(project="example")
    assert config.schema_version == 1
    assert config.model.default_profile is None
    assert config.model.profiles == {}
    assert config.documentation.mode == "suggest"
    assert config.mcp.enabled is False
    assert config.mcp.tool_set == "read-only"


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": 2},
        {"schema_version": True},
        {"schema_version": 1.0},
        {"unexpected": "not allowed"},
        {"profiles": ["terraform"]},
        {"profiles": ["python", "python"]},
        {"mcp": {"enabled": "false"}},
        {"documentation": {"mode": "automatic"}},
        {"context_limits": {"max_file_bytes": 0}},
        {"context_limits": {"max_file_bytes": 10, "max_total_bytes": 1}},
        {"check_policy": {"required": ["missing"]}},
        {"model": {"default_profile": "missing"}},
        {"tasks": {"bad": {"argv": "pytest"}}},
        {"tasks": {"bad": {"argv": [""]}}},
        {"tasks": {"bad": {"argv": ["pytest"], "timeout_seconds": -1}}},
        {"tasks": {"bad": {"argv": ["server"], "side_effect": "local-service"}}},
    ],
)
def test_invalid_configuration_is_rejected(change):
    with pytest.raises(ValidationError):
        ProjectConfig.model_validate({"project": "example", **change})


@pytest.mark.parametrize(
    "path",
    [
        "../outside",
        "/tmp/outside",
        "C:/outside",
        "a\\b",
        ".env",
        ".env.local",
        ".git/config",
        ".ssh/id_rsa",
        "secret.pem",
        "x.tfstate.backup",
        ".ai/local/context.json",
    ],
)
def test_sensitive_and_escaping_paths_are_denied(path):
    with pytest.raises(ValueError):
        relative_path(path)


def test_whole_task_replacement_and_array_precedence():
    lower = {
        "profiles": ["node"],
        "tasks": {"test": {"argv": ["npm", "test"], "timeout_seconds": 99}},
        "documentation": {"mode": "off", "changelog": "CHANGES.md"},
    }
    higher = {
        "profiles": ["python"],
        "tasks": {"test": {"argv": ["uv", "run", "pytest"]}},
        "documentation": {"mode": "suggest"},
    }
    result = merge(lower, higher)
    assert result["tasks"]["test"] == {"argv": ["uv", "run", "pytest"]}
    assert result["profiles"] == ["python"]
    assert result["documentation"]["changelog"] == "CHANGES.md"
    assert lower["tasks"]["test"]["timeout_seconds"] == 99


def test_generated_schema_matches_checked_in_reference():
    root = Path(__file__).resolve().parents[1]
    assert (
        json.loads((root / "docs/project.schema.json").read_text())
        == ProjectConfig.model_json_schema()
    )


def test_roundtrip_and_schema_validation():
    original = ProjectConfig(project="example", tasks={"test": {"argv": ["custom", "--test"]}})
    data = original.model_dump()
    Draft202012Validator.check_schema(ProjectConfig.model_json_schema())
    Draft202012Validator(ProjectConfig.model_json_schema()).validate(data)
    assert ProjectConfig.model_validate_json(original.model_dump_json()) == original


def test_credentials_in_endpoint_and_unknown_fields_are_not_echoed(tmp_path):
    for data in [
        {"project": "example", "SUPER_SECRET_VALUE": "private"},
        {
            "project": "example",
            "model": {
                "profiles": {
                    "x": {
                        "adapter": "ollama",
                        "model": "model",
                        "endpoint": "https://user:SUPER_SECRET_VALUE@host",
                    }
                }
            },
        },
    ]:
        with pytest.raises(SetupError) as caught:
            validate(tmp_path, data)
        assert "SUPER_SECRET_VALUE" not in str(caught.value)


@pytest.mark.parametrize("data", [b'{"a":1,"a":2}', b"[]", b"{", b"\xff"])
def test_invalid_json_is_rejected_without_raw_input(data):
    with pytest.raises(SetupError):
        parse_json(data)


def test_approved_node_example_passes_model_and_structural_schema(tmp_path):
    fixture = Path(__file__).parent / "fixtures/project-node.json"
    data = json.loads(fixture.read_text())
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/architecture.md").write_text("Architecture")
    (tmp_path / "CONTRIBUTING.md").write_text("Guidance")
    config = validate(tmp_path, data)
    Draft202012Validator(ProjectConfig.model_json_schema()).validate(config.model_dump())
    assert config.tasks["dev"].lifecycle == "service"
    assert config.model.default_profile is None
