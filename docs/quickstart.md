# Local package, configuration and safe initialization

Development increment: Step 04B, version 0.1.0.dev1. This is an unpublished
candidate identity. Help/version, configuration validation/schema and create-only
initialization are implemented. Task execution, doctor, context tools, model calls,
pack/lock management and MCP remain subsequent increments.

## Prerequisites and setup

Python 3.12 through uv, Git and a terminal. Run these from portable-ai-harness.
The committed uv.lock pins runtime/development dependencies. Installation/build can
contact the configured package index; the implemented harness commands do not.

```bash
uv sync --locked
uv run --locked pah --help
uv run --locked pah --version
uv run --locked pah version --json
```

The version is read from installed distribution metadata, not a duplicate source
constant. JSON version reports use report_schema 1 with distribution, cli_version
and python_version. Project schema_version is a separate identity.

## Safe initialization

```bash
uv run --locked pah init --dry-run
uv run --locked pah init
uv run --locked pah config validate
uv run --locked pah config schema
```

Init prints its exact proposed configuration before asking to create it. Answer
no or send EOF to stop without writing. --dry-run does not even create .ai.
For explicitly approved CLI automation, --yes accepts the displayed create
proposal. This CLI option is not a model-authored approval token or a future MCP
approval mechanism. MCP's trusted approval channel remains unimplemented.

Only .ai/project.json is created. Existing manifests are validated and preserved
byte-for-byte; overrides/templates are not applied on rerun. Update/migration is
not implemented. Commit the reviewed manifest as project-owned configuration.
Init never runs tasks/scripts/hooks, imports project code, installs toolchains,
loads environment credentials, contacts a provider or changes Git state.

```bash
uv run --locked pah init --root ./another-project --dry-run
uv run --locked pah init --profile python --project example --dry-run
uv run --locked pah init --config-template ./team-harness.json --dry-run
```

--root selects an existing project directory; template paths are relative to that
selected root. Explicit profile options replace the discovered profile list.
Currently supported definitions are python and node. Other languages can use
profiles [] and explicit argv tasks; Maven/Terraform metadata are hints only.

Precedence for new manifests: explicit options, local template, discovery,
defaults. Lists replace; ordinary maps merge; each higher-precedence task replaces
the whole task, so argv/cwd do not accidentally combine with lower defaults.
Templates are bounded JSON data and reject unknown fields. Configuration must not
contain secrets: credential_env stores an environment variable NAME, never its value.

Python/uv discovery uses pyproject.toml and uv.lock/tool.uv evidence, with declared
pytest/ruff dependencies and build metadata. Group selection needs review;
discovery does not prove those tools are installed in the active environment.
Node discovery reads actual script names and package-manager declarations. It
does not append guessed runner flags; check watch modes before enabling tasks.
Conflicting Python/Node task names or ambiguous package-manager choices require
a template that resolves the tasks, rather than an invented command.

## Schema and boundaries

ProjectConfig is the strict validation model. docs/project.schema.json and
pah config schema derive structural JSON Schema from that same model. Tests check
reference drift and validate the approved Node fixture with both validators.
Cross-field references, additional path policy and filesystem checks are enforced
by the core; standalone JSON Schema validation does not perform those checks.

The model includes future tasks/model/documentation/MCP settings for the approved
contract. Accepting their data does not implement or authorize the corresponding
features. Model defaults are null/empty; docs default to suggest and MCP to disabled
read-only. Required checks must refer to defined tasks; none is marked passing.

Metadata reads are capped at 128000 bytes. Unknown fields/schema versions,
malformed data, missing required paths, credential/parent-traversal paths and
symlinks are rejected. Exclusion patterns cannot disable built-in sensitive-path
denials. Errors do not echo rejected configuration values. Review valid config
previews before sharing them; validation is not a detector of every secret a user
might incorrectly embed in an otherwise valid string.

Initial safe writes target macOS/Linux using directory-relative, no-follow access
and create-only publication of complete bytes. They refuse intervening files or
symlinks rather than replace them. Windows write support is not yet implemented;
its portability requires separate work/tests. The policy protects harness actions,
not arbitrary external assistant tools or concurrent privileged host attackers.

No packs, .ai/harness.lock.json or editor instructions are installed by this
increment. The default base-pack name is configuration intent, not an installed pack.

## Validation and package installation

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest -q
uv build
uv run --locked python scripts/smoke_install.py
```

The smoke check installs the built wheel in a disposable environment and exercises
version/help, dry-run, creation, validation, rerun preservation and schema output
outside the source checkout. It removes the temporary environment and does not
replace a global pah installation. Development uses uv run.

Isolated build-backend resolution uses the bounded build-system requirement,
not the uv dependency lock. Later provenance records build tooling; this is not
claimed to be a fully hermetic or byte-identical build. Exit codes implemented here:
0 success, 1 declined creation, 2 usage/configuration errors, 3 path/filesystem
policy denial, 4 unavailable safe-write platform. EOF exits nonzero without writes.

## Package boundaries and next work

core/config.py owns data/schema, core/setup.py owns metadata/discovery and init,
core/version.py owns installed identity, and cli.py handles terminal requests,
rendering and confirmation. Future MCP adapters call shared services directly and
add their tested trusted approval route; they never parse CLI output or forward --yes.
Task execution/readiness follows in Step 04C; CI automation follows in 04D.

## References

- [Configuration and command design](configuration-and-commands.md)
- [Approved MCP amendment](mcp-scope-amendment.md)
- [Pydantic model configuration](https://docs.pydantic.dev/latest/concepts/config/)
- [uv projects](https://docs.astral.sh/uv/guides/projects/)
- [Typer confirmation](https://typer.tiangolo.com/tutorial/prompt/)

## Optional token controls

Input and output token budgets are independently optional, disabled by default
with null. Set a positive integer to opt into either control. Existing explicit
numbers remain enabled until deliberately changed; init never resets them.
Byte/file limits and secret/path restrictions remain separate safeguards.
This increment validates configuration only; model/token execution follows later.
Disabling user budgets does not bypass provider context limits, required API
parameters or provider/platform quotas. Token counting/estimation will not be
required for the CLI's offline configuration and task tooling.
