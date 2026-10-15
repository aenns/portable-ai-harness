# Portable AI Harness: product scope

## Status

Step 04B adds strict project configuration/schema, bounded Python/uv and Node discovery, preview and create-only initialization to the existing CLI. Mac validation is recorded in progress/checkpoints.md. Configuration data for future tasks/models/MCP does not implement or authorize those features; CI, stable release and cloud deployment remain future work.

## Purpose

A reusable development toolbox for inspecting projects, preparing AI context, running reviewed tasks and recording validation evidence.

## Planned stack

Python 3.12, uv, Typer and Pydantic

## Engineering contract

- This repository owns its source, checks, documentation and releases.
- Public interfaces are versioned and tested.
- The development harness is optional tooling, not a runtime dependency.
- Examples and demonstration data are synthetic.
- Architecture decisions and exact local commands will be documented
  as their implementation checkpoints pass.

## Approved design baseline

- Python implements the harness; project-owned argv tasks support other installed languages and infrastructure tooling.
- Assistant-led and direct-model workflows share context, specifications, checks and evidence; direct-model changes require reviewed local approval.
- Initial fake/Ollama/OpenAI/Anthropic adapters are planned. Compatibility is tested per adapter/client; universal IDE/model compatibility is not claimed.
- Optional local stdio MCP follows the validated CLI and targets the same supported core capabilities, including reviewed writes/tasks/checkpoints. Read-only is the default; client/approval support is tested and documented. See [MCP amendment](mcp-scope-amendment.md). Installed version, configuration schema and candidate artifacts are versioned.
- Feature specifications and project conventions guide implementation, tests and review. Documentation supports off/suggest/update modes with reviewed writes.
- Secret context denial, bounded output/time/token budgets and checkpoint offers are required; approved commands still run with local user privileges.
- Use candidate harness builds for RelayCart development and capture feedback before stable promotion and public launch.

## Required engineering evidence

Each component has applicable automated checks: unit, integration, functional/contract and security tests; dependency/container/IaC scanning and secret detection where relevant. Main builds, deployments, scheduled regressions and availability observations are distinct. Build/candidate numbers increment automatically; stable semantic versions are calculated from reviewed changes and promoted through the release-readiness gate. Retain immutable artifacts, sanitized evidence and compatible rollback instructions. These are requirements, not implementation claims.

Use the portable harness during development once its core is usable; record any bypasses and feedback. The application does not import the harness at runtime.

## Design references

- [Harness release scope](https://github.com/aenns/portable-ai-harness/blob/96cc799/docs/release-scope.md)
- [Harness architecture](https://github.com/aenns/portable-ai-harness/blob/40476cf/docs/architecture.md)
- [Harness configuration and commands](https://github.com/aenns/portable-ai-harness/blob/99d47a1/docs/configuration-and-commands.md)
- [RelayCart system architecture, revision 4](https://github.com/aenns/relaycart-docs/blob/f5cf12d/docs/architecture/system.md)
