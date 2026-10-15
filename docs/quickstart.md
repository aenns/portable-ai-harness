# Step 04A — local package and CLI

This development increment supplies CLI help and installed version reporting only.
Project discovery/configuration, execution, AI workflows and MCP follow later.
Version 0.1.0.dev0 is an unpublished development identity, not a stable release.

## Prerequisites and setup

Python 3.12 through uv, Git and a terminal. Run from portable-ai-harness.
The committed uv.lock pins resolved dependencies; use locked commands for validation.
Installation/build may contact the configured package index; version/help commands do not.

```bash
uv sync --locked
uv run --locked pah --help
uv run --locked pah --version
uv run --locked pah version
uv run --locked pah version --json
```

The version option prints Portable AI Harness 0.1.0.dev0. The detailed report also
identifies the Python runtime. --json emits report_schema, distribution,
cli_version and python_version; it contains no environment dump or credentials.
No pack/project schema version is claimed before those components exist.

## Validation

```bash
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest -q
uv build
uv run --locked python scripts/smoke_install.py
```

Unit/CLI tests verify identity, errors, help and JSON behavior. The smoke check
installs the built wheel into a temporary environment and invokes its CLI/module
entry points outside the checkout, then removes that environment. It does not
install a global pah command or overwrite an existing uv tool installation.
The source checkout uses uv run; distributable installation is proved by the smoke test.

The lockfile pins runtime/development dependencies. Isolated build-backend
resolution currently follows the bounded build-system requirement, not that lock.
Record tooling/build versions in later release provenance; do not call this a
fully hermetic or byte-identical build.

## Package boundaries and extension

- src/portable_ai_harness/core/version.py owns immutable version facts using installed metadata.
- cli.py translates those facts to terminal/JSON output through Typer.
- __main__.py supports python -m portable_ai_harness.
- pyproject.toml is the authoritative product version; code does not duplicate it.
- A future MCP adapter calls core services directly, not the CLI subprocess.
- Pydantic/configuration and provider dependencies are added with their features.

No project files are edited by these commands. No model keys, service accounts,
Docker daemon or cloud account are required. Missing metadata fails with an
installation instruction rather than inventing a version. Actual CLI task
execution and its security boundaries are not implemented in this increment.

## References

- [uv projects](https://docs.astral.sh/uv/guides/projects/)
- [Typer version options](https://typer.tiangolo.com/tutorial/options/version/)
- [Hatch build configuration](https://hatch.pypa.io/latest/config/build/)
- [Approved MCP scope](mcp-scope-amendment.md)
