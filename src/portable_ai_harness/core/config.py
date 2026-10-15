"""Strict version-one project data; no provider SDK, environment loading or task execution."""

from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Positive = Annotated[int, Field(gt=0, le=10_000_000)]
Name = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")]


class Data(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def relative_path(value: str) -> str:
    """Reject nonportable, escaping and built-in sensitive paths independent of excludes."""
    parts = PurePosixPath(value).parts
    if (
        not value
        or "\\" in value
        or "\x00" in value
        or PurePosixPath(value).is_absolute()
        or PureWindowsPath(value).drive
        or ".." in parts
        or any(
            part.lower() in {".git", ".ssh", ".aws", ".azure", ".ai-local"}
            or part.lower()
            in {".env", ".npmrc", ".pypirc", ".netrc", ".dev.vars", "credentials.json"}
            or part.lower().startswith(".env.")
            or part.lower().endswith((".pem", ".key", ".tfplan"))
            or ".tfstate" in part.lower()
            or part.lower() in {"id_rsa", "id_ed25519"}
            for part in parts
        )
        or tuple(part.lower() for part in parts[:2]) == (".ai", "local")
    ):
        raise ValueError("use a workspace-relative, non-sensitive path without parent traversal")
    return value


class Instructions(Data):
    paths: list[str] = Field(default_factory=list, max_length=100)
    default_pack: Name = "base"


class ContextLimits(Data):
    max_file_bytes: Positive = 32000
    max_total_bytes: Positive = 128000
    input_token_budget: Positive | None = None
    output_token_budget: Positive | None = None

    @model_validator(mode="after")
    def bounded(self):
        if self.max_file_bytes > self.max_total_bytes:
            raise ValueError("max_file_bytes must not exceed max_total_bytes")
        return self


class ModelProfile(Data):
    adapter: Literal["fake", "ollama", "openai", "anthropic"]
    model: Annotated[str, Field(min_length=1, max_length=256)]
    endpoint: str | None = None
    credential_env: Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")] | None = None
    timeout_seconds: Annotated[int, Field(gt=0, le=3600)] = 30

    @model_validator(mode="after")
    def endpoint_is_data(self):
        if self.endpoint is not None:
            parsed = urlsplit(self.endpoint)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("endpoint must be HTTP(S) without credentials, query or fragment")
        return self


class Models(Data):
    default_profile: Name | None = None
    profiles: dict[Name, ModelProfile] = Field(default_factory=dict, max_length=100)

    @model_validator(mode="after")
    def known_default(self):
        if self.default_profile is not None and self.default_profile not in self.profiles:
            raise ValueError("default_profile must name a configured model profile")
        return self


class Task(Data):
    argv: Annotated[list[str], Field(min_length=1, max_length=100)]
    cwd: str = "."
    timeout_seconds: Annotated[int, Field(gt=0, le=3600)] = 120
    side_effect: Literal["local-check", "local-build", "local-service"] = "local-check"
    lifecycle: Literal["task", "service"] = "task"

    @model_validator(mode="after")
    def valid_task(self):
        if not self.argv[0].strip() or any("\x00" in arg for arg in self.argv):
            raise ValueError("argv requires a nonempty executable and no NUL bytes")
        relative_path(self.cwd)
        if self.lifecycle == "service" and self.side_effect != "local-service":
            raise ValueError("service lifecycle requires local-service side_effect")
        if self.side_effect == "local-service" and self.lifecycle != "service":
            raise ValueError("local-service requires service lifecycle")
        return self


class Checks(Data):
    required: list[Name] = Field(default_factory=list, max_length=100)
    optional: list[Name] = Field(default_factory=list, max_length=100)


class GitCheckpoint(Data):
    mode: Literal["ask-if-dirty", "always", "off"] = "ask-if-dirty"


class Documentation(Data):
    mode: Literal["off", "suggest", "update"] = "suggest"
    feature_output: str = "docs/features"
    changelog: str = "CHANGELOG.md"


class MCP(Data):
    enabled: bool = False
    tool_set: Literal["read-only", "reviewed"] = "read-only"


class ProjectConfig(Data):
    """Persistable configuration, not proof that configured features are implemented/authorized."""

    schema_version: Literal[1] = 1
    project: Name
    workspace_root: Literal["."] = "."
    profiles: list[Literal["python", "node"]] = Field(default_factory=list, max_length=2)
    exclude: list[str] = Field(
        default_factory=lambda: [
            ".env",
            ".env.*",
            ".git",
            ".venv",
            "node_modules",
            ".ai/local",
            "*.tfstate",
            "*.tfplan",
        ],
        max_length=100,
    )
    instructions: Instructions = Field(default_factory=Instructions)
    context_limits: ContextLimits = Field(default_factory=ContextLimits)
    model: Models = Field(default_factory=Models)
    tasks: dict[Name, Task] = Field(default_factory=dict, max_length=100)
    check_policy: Checks = Field(default_factory=Checks)
    git_checkpoint: GitCheckpoint = Field(default_factory=GitCheckpoint)
    documentation: Documentation = Field(default_factory=Documentation)
    mcp: MCP = Field(default_factory=MCP)

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_schema(cls, value):
        if type(value) is not int:
            raise ValueError("schema_version must be integer 1")
        return value

    @model_validator(mode="after")
    def references_and_paths(self):
        if len(set(self.profiles)) != len(self.profiles):
            raise ValueError("profiles must be unique")
        if set(self.check_policy.required) - self.tasks.keys():
            raise ValueError("every required check must name a defined task")
        if set(self.check_policy.required) & set(self.check_policy.optional):
            raise ValueError("a check cannot be both required and optional")
        for path in [
            *self.instructions.paths,
            self.documentation.feature_output,
            self.documentation.changelog,
        ]:
            relative_path(path)
        return self
