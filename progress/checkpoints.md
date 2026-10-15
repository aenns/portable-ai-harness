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

## Step 04C — doctor, bounded tasks/checks and local reports

Date: 15 October 2026
Status: cross-platform correction prepared; corrected Mac and all three native CI results PENDING.

- Read-only doctor and run/check previews; explicit terminal approval precedes task execution.
- Named literal argv, selected cwd, revalidated manifest/path/executable, output/time bounds and owned process-group cleanup.
- Required/optional outcomes, original exits and failures are retained accurately; local reports omit raw output/argv and enforce capacity/size bounds.
- Preparation: 134 tests, lint/format, package build, installed-wheel workflow and harness self-check passed on Linux Python 3.12; not Mac evidence.
- Required Mac checks: locked sync; lint/format/tests; package build/smoke; doctor, previews, actual named run/check and report read; ignored local reports and null token budgets verified.
- Record actual Mac evidence before marking PASS. Model/MCP, service lifecycle, feature acceptance and CI remain unimplemented.

### Step 04C portability correction

- Windows, macOS and Linux are first-release requirements; Windows is not deferred.
- Initial Mac run: 133 passed, 1 process-cleanup failure; build correctly skipped.
- Correction adds verified POSIX cleanup, Windows Job Object execution, bounded pipe capture, native safe init/report storage, portable path rules and three-platform acceptance CI.
- Linux preparation: 164 passed, 7 native Windows tests skipped; lint/format, build and installed-wheel smoke passed. These results are not Windows/macOS evidence.
- Corrected local Mac run and hosted Linux/macOS/Windows acceptance: PENDING. Record source commit, run URLs and actual outcomes before marking PASS or merging.
- No new release; version stays 0.1.0.dev2. Token budgets remain optional; the manifest, lockfile and original task approval boundaries are preserved.
- See docs/portability.md; wider release/security CI remains Step 04D.

### Corrected Mac acceptance — 15 October 2026

- Harness check PASS: lint, test and build exited 0; cleanup confirmed for all three.
- Installed-wheel init/config/doctor/run/check/report smoke PASS.
- git diff --check passed.
- Evidence report: 20261015T223240909736Z-8a7bc439d75542378994f4db4f1cf854
- Hosted Windows, macOS and Linux acceptance remains pending; do not merge yet.

### Step 04C Windows CI correction

- Initial native CI source: 02e7c001d46cc3203d1b3ee710bc88f600d745c3.
- Hosted Ubuntu and macOS PASS reported by Adrian; Windows: 165 passed, 2 failed, 4 skipped.
- Failures: unsupported os.mkfifo fixture and ineffective metadata-only directory handles.
- Correction: Unix capability guard for FIFO only, GENERIC_READ directory handles without delete sharing, shared flag regression, and stronger native pin/unpin assertions.
- Linux preparation: 165 passed, 7 native Windows tests skipped; lint/format, build and installed-wheel smoke passed. Native Windows rerun is required, including build/smoke/self-check.
- All three CI jobs on the correction commit remain PENDING. Do not merge until they pass.
- Version remains 0.1.0.dev2; configuration, token settings and lockfile unchanged.
