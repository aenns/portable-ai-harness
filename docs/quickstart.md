# Local package, configuration and safe initialization

Development increment: Step 04C, version 0.1.0.dev2. This is an unpublished
candidate identity. Help/version, configuration validation/schema and create-only
initialization are implemented, together with doctor and bounded named tasks/checks/reports.
Context tools, model calls, pack/lock management and MCP remain subsequent increments.

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

The model includes task settings plus future model/documentation/MCP settings
for the approved contract. Accepting data alone never authorizes execution or
implements those later features. Model defaults are null/empty; docs default to suggest and MCP to disabled
read-only. Required checks must refer to defined tasks; none is marked passing.

Metadata reads are capped at 128000 bytes. Unknown fields/schema versions,
malformed data, missing required paths, credential/parent-traversal paths and
symlinks are rejected. Exclusion patterns cannot disable built-in sensitive-path
denials. Errors do not echo rejected configuration values. Review valid config
previews before sharing them; validation is not a detector of every secret a user
might incorrectly embed in an otherwise valid string.

Create-only writes use directory-relative no-follow access on macOS/Linux and
pinned native directory/file handles on Windows. Windows rejects junctions and
other reparse points, and new files use a protected current-user/LocalSystem DACL.
Existing directories are not silently repermissioned. The baseline is a local
workspace (NTFS on Windows); network shares are outside the tested contract.
These boundaries protect harness operations, not arbitrary project tools or a
concurrent privileged host attacker. See [portability](portability.md).

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
Task execution/readiness is described below; CI automation follows in 04D.

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

## Step 04C — doctor and bounded execution

Version 0.1.0.dev2 adds these implemented commands:

```bash
uv run --locked pah doctor
uv run --locked pah doctor --json
uv run --locked pah run lint --dry-run
uv run --locked pah check --dry-run
uv run --locked pah run lint
uv run --locked pah check
uv run --locked pah report
```

Doctor inspects configured executable presence and path/data validity without
executing project commands, hooks, model calls or network probes. AVAILABLE means
the launcher exists, not that nested tools/versions or tests work. Missing required
launchers exit 4; absent check configuration is labelled NOT_CONFIGURED.

Run/check show task argv, cwd, limits, effects and configuration fingerprint before
confirmation. Decline or EOF executes nothing. Explicit --yes is local CLI consent,
not a future MCP approval token. Run accepts a configured task NAME only, never a
shell string. The runner uses shell=False, a selected cwd and an owned new process
group. Named project programs can still invoke shells, read files or use the
network; review them as trusted user-level code. This is not a sandbox.

Each task has timeout_seconds and max_output_bytes (default 65536; maximum 1048576,
shared across stdout/stderr). A timeout or output overflow fails and stops the
owned process group; it is not a truncated PASS. Original exit codes/signals and
reason codes remain in the report. Ctrl-C attempts cleanup and exits 130. Ordinary
background children in the group are cleaned up; deliberately detached processes
and concurrent privileged host attackers are outside this mechanism's guarantees.
Service tasks are refused here; dev start/status/stop is a later lifecycle feature.

Task env defaults to a small toolchain/locale/home/temp allowlist. Explicit
Task.env_allow entries can forward selected additional environment-variable names;
values are never printed in the task preview. No .env is loaded by the harness.
Approved programs can access the user's filesystem and credentials themselves.
Known forwarded secret values are masked in displayed output as a best effort,
not universal secret detection. Arbitrary output may still be private: review it
before sharing. Raw stdout/stderr and argv are not stored in outcome reports.

Check runs configured required checks followed by optional checks. A required
failure stops later work with SKIPPED outcomes. Missing optional checks are
NOT_CONFIGURED; optional task failures remain FAIL but do not fail the required
check aggregate. Cancellation or changed policy/configuration stops the run.
No required checks means check refuses to invent a passing result. Configuration
changes after preview invalidate the plan. Task source files are not frozen:
these outcomes do not establish acceptance of an immutable feature/source snapshot.

Reports live in .ai/local/reports with private files and bounded reads/writes;
ensure /.ai/local/ is ignored by Git in each consumer. `report` reads the newest
timestamped report, or pass an explicit ID printed by run/check. It never re-runs
tasks. Reports include run ID, time, harness version, config hash, task outcomes,
exit codes, duration and output counts; they do not prove feature acceptance.
A 100-report cap stops new execution until older local reports are deliberately
reviewed/removed. No automatic deletion of existing evidence is performed.

Windows, macOS and Linux are first-release targets. The platform backends and
three-runner acceptance workflow are implemented; support is not considered
validated until each native CI job passes. No WSL requirement is imposed.
The Mac cleanup regression is fixed with state verification rather than ignoring
permission errors. Unconfirmed cleanup produces FAIL/CLEANUP_UNCONFIRMED.
No model is required; optional token budgets remain null unless explicitly set.
MCP, feature workflows, long-running development services and the wider release/
security CI pipeline remain future increments. This correction adds portability CI. The existing version-one schema adds optional env_allow and
max_output_bytes task settings with defaults; existing manifests remain valid.

Validation adds real subprocess/CLI/filesystem fixtures for failures, timeouts,
output bounds, environment handling, approval, report safety and child cleanup.
The wheel smoke check also exercises doctor/run/check/report outside the checkout.


## Windows terminal

With Python 3.12 and uv installed, use PowerShell in the repository root:

```powershell
uv sync --locked
uv run --locked pah --version
uv run --locked pah doctor
uv run --locked pah check --dry-run
uv run --locked pah check
uv run --locked python scripts/smoke_install.py
uv run --locked pah report
```

No environment activation or Unix shell is needed. Manifest paths use forward
slashes on every OS; task argv is an argument array, not a shell command string.
Standard npm.cmd installs are adapted to node.exe plus npm-cli.js; other batch
shims need an explicitly reviewed interpreter in argv. Shell syntax is never
silently enabled. Tool availability still depends on what the user installs.
