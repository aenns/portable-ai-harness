# Checkpoints

Repository: portable-ai-harness

## Step 02 — Repository baseline

- Public repository created and cloned.
- Correct origin and clean main branch verified.
- Baseline files created on a development branch.
- Commit, push and baseline merge validation: PASS (verified from supplied Git output).
- Application implementation: NOT STARTED.

## Step 03 — Approved design checkpoint

Review date: 7 October 2026

- Scope, service/data ownership and documented interfaces: design review PASS.
- Security/gateway/secrets, RAG, observability, testing/scanning and release requirements recorded.
- Free cloud and tested self-hosted portability are implementation targets; paid hosting is optional.
- This documentation change records Step 03C; publication is evidenced by its merged PR and subsequent clean main verification.
- Application/harness implementation, CI pipelines and cloud deployment: NOT STARTED.

Approved design sources:

- [Harness release scope](https://github.com/aenns/portable-ai-harness/blob/96cc799/docs/release-scope.md)
- [Harness architecture](https://github.com/aenns/portable-ai-harness/blob/40476cf/docs/architecture.md)
- [Harness configuration and commands](https://github.com/aenns/portable-ai-harness/blob/99d47a1/docs/configuration-and-commands.md)
- [RelayCart system architecture, revision 4](https://github.com/aenns/relaycart-docs/blob/f5cf12d/docs/architecture/system.md)

## MCP scope amendment — 15 October 2026

- Decision agreed in conversation on 11 October; recorded before Step 04 implementation.
- CLI first, one shared core, full supported CLI/MCP capability parity target.
- Read-only default; reviewed operations require tested human approval and client compatibility.
- [Amendment](../docs/mcp-scope-amendment.md) defines precedence and acceptance; Step 03's completed checkpoint remains valid.
- Implementation and compatibility evidence: NOT STARTED; design approval is not a test result.
- Publication is evidenced by this change's merged PR and clean main verification.

## Step 04A — package and CLI foundation

Date: 15 October 2026
Status: PASS for local Mac validation; publication is evidenced by the containing merged PR.

- Shared transport-independent version service and Typer CLI provide help/version/JSON.
- Product version is read from installed distribution metadata, not duplicated in code.
- Unit/CLI tests, locked development dependencies and isolated wheel-install smoke check are included.
- Linux Python 3.12 validation was performed during preparation; it is not Mac compatibility evidence.
- Required Mac checks: uv sync --locked; CLI help/version/JSON; Ruff lint/format; pytest; uv build; scripts/smoke_install.py.
- Supplied Mac results: Ruff lint PASS; formatting PASS; 13 tests PASS; wheel/sdist build PASS; isolated wheel-install smoke check PASS.
- Later configuration, execution, models, MCP and CI/release work remain unimplemented.

## Step 04B — configuration and safe initialization

Date: 15 October 2026
Status: PASS for local Mac validation; publication is evidenced by the containing merged PR.

- Strict schema-version-one ProjectConfig, generated structural schema and tested cross-field/path rules.
- Bounded Python/uv and Node metadata discovery; explicit overrides/template precedence; no task execution or toolchain installation.
- Reviewable dry-run and confirmation; only .ai/project.json is created, never overwritten on rerun.
- Filesystem fixtures cover symlink/escape/oversize/FIFO denial, concurrent destination creation and preserved existing bytes.
- Preparation validation: 92 tests, lint/format, wheel/sdist and installed CLI init/config smoke passed on Linux Python 3.12; this is not Mac evidence.
- Required Mac checks: locked sync; lint/format/tests; build and isolated smoke; own-project init preview/create/validate/rerun preservation.
- Supplied Mac results: lint/format PASS; 92 tests PASS; wheel/sdist build PASS; installed init/config smoke PASS; own-project validation and rerun preservation PASS. Doctor/tasks/model/MCP/CI remain unimplemented.

### Step 04B clarification — optional token controls

Input/output budgets are independently optional, default null. Added eight tests
for defaults, independent opt-in, round trips and invalid enabled values. The
self-hosting project manifest deliberately disables both user budgets; byte and
path safeguards remain. Mac validation subsequently passed: 92 tests, lint/format, builds, installed smoke and configuration validation.
