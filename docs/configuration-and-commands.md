# Portable AI Harness — Configuration and command contracts

Design revision: 2
Checkpoint: Step 03B, section 2
Date: 7 October 2026
Status: approved design contracts; commands and schema are not implemented yet.

Read this with [release-scope.md](release-scope.md) and [architecture.md](architecture.md). The architecture was merged at commit `40476cf`. This document adds configurable feature documentation to that design. Examples are intended test fixtures, not configuration that can be run today. Generated JSON Schema and exact CLI help will become authoritative when implemented and tested.

## Configuration ownership

| File/location | Purpose | Ownership |
|---|---|---|
| `.ai/project.json` | Validated project identity, reviewed tasks, instructions, context, model profiles and documentation behaviour | Developer-owned, committed |
| `.ai/harness.lock.json` | Exact packs, hashes, schema/CLI compatibility and explicitly installed extension references | Harness-managed, committed, updates reviewed |
| `.ai/policies/` and prompt pack files | Versioned bundled guidance | Managed inventory; edited files become upgrade conflicts |
| Project-selected instruction files | Organization/project conventions and examples | Developer-owned; never overwritten during pack upgrade |
| `features/<ID>/feature.json` | Outcome, criteria, selected context and checks | Developer-owned, committed |
| `features/<ID>/spec.md` | Optional readable narrative/examples | Developer-owned, committed |
| `.ai/local/` | Context previews, proposals, state fingerprints, reports, cache and recovery data | Local, ignored; bounded cleanup and sensitive-source handling |
| Environment variables / local credential store | Provider secrets | Never embedded in project/lock/report files |

The installed CLI version and machine executable paths are observed locally, not hard-coded into a portable project configuration. The lock records compatibility rather than pretending that the project can silently replace the installed CLI.

## Proposed project example

This fixture assumes a Node project has actual `lint`, `types`, Vitest-compatible `test`, `build` and `dev` scripts. Discovery does not create scripts or claim these checks exist in today's empty repos. Another language changes the profiles/tasks, not the shared harness.

```json
{
  "schema_version": 1,
  "project": "example-typescript-project",
  "workspace_root": ".",
  "profiles": [
    "node"
  ],
  "exclude": [
    ".env",
    ".env.*",
    ".git",
    "node_modules",
    ".ai/local",
    "*.tfstate",
    "*.tfplan"
  ],
  "instructions": {
    "paths": [
      "CONTRIBUTING.md",
      "docs/architecture.md"
    ],
    "default_pack": "base"
  },
  "context_limits": {
    "max_file_bytes": 32000,
    "max_total_bytes": 128000,
    "input_token_budget": 6000,
    "output_token_budget": 1500
  },
  "model": {
    "default_profile": null,
    "profiles": {
      "offline-demo": {
        "adapter": "fake",
        "model": "deterministic-v1",
        "timeout_seconds": 30
      },
      "local": {
        "adapter": "ollama",
        "model": "REPLACE_WITH_INSTALLED_MODEL",
        "endpoint": "http://localhost:11434",
        "timeout_seconds": 90
      }
    }
  },
  "tasks": {
    "lint": {
      "argv": [
        "npm",
        "run",
        "lint"
      ],
      "cwd": ".",
      "timeout_seconds": 120,
      "side_effect": "local-check"
    },
    "types": {
      "argv": [
        "npm",
        "run",
        "types"
      ],
      "cwd": ".",
      "timeout_seconds": 120,
      "side_effect": "local-check"
    },
    "test": {
      "argv": [
        "npm",
        "run",
        "test",
        "--",
        "--run"
      ],
      "cwd": ".",
      "timeout_seconds": 120,
      "side_effect": "local-check"
    },
    "build": {
      "argv": [
        "npm",
        "run",
        "build"
      ],
      "cwd": ".",
      "timeout_seconds": 180,
      "side_effect": "local-build"
    },
    "dev": {
      "argv": [
        "npm",
        "run",
        "dev"
      ],
      "cwd": ".",
      "timeout_seconds": 30,
      "side_effect": "local-service",
      "lifecycle": "service"
    }
  },
  "check_policy": {
    "required": [
      "lint",
      "types",
      "test",
      "build"
    ],
    "optional": []
  },
  "git_checkpoint": {
    "mode": "ask-if-dirty"
  },
  "documentation": {
    "mode": "suggest",
    "feature_output": "docs/features",
    "changelog": "CHANGELOG.md"
  },
  "mcp": {
    "enabled": false,
    "tool_set": "read-only"
  }
}
```

### Validation rules

- Reject malformed/unknown schemas and unknown fields with actionable errors. Generate JSON Schema from the same validation models used by the CLI; do not separately hand-maintain competing definitions.
- Resolve workspace/context/output paths relative to a fixed project root. Reject escape, denied paths, symlink escape and invalid target types. Built-in sensitive-path denials are retained even if project exclusions omit them.
- Task argv arrays contain literal arguments, not shell strings. Validate executable/cwd/timeout; a side-effect label is descriptive, not an OS sandbox. Named programs and project code must be trusted.
- Every required check must resolve to a defined task. A missing required executable/task fails readiness. Optional absent tasks may be skipped; skipped/unconfigured tasks are never counted as passing.
- Model default is null. Inspection/checks/docs summaries work without inference. Explicitly selected hosted profiles need environment-variable references and capabilities validated before calls.
- Endpoint/model selection comes from reviewed settings/explicit user selection, not arbitrary instructions found in source or returned by a model. No silent provider fallback or toolchain/plugin installation.
- Token budgets include instructions and protocol overhead within the input allowance, reserve output, and fit the selected adapter's declared model limit with headroom. Unknown limits/counts are reported as estimates/unknown; do not promise exact fit. Byte limits remain independent safeguards.
- `doctor` validates local readiness without running project checks or network calls. Provider/network checks require an explicit selection.
- Resolve requested read-only MCP enablement separately from the actual server start command. The initial tool set cannot be expanded to mutation/execution merely by editing a string.

## Initialization and discovery

`pah init` discovers project conventions by default and accepts explicit configuration overrides. A repository may use multiple profiles; do not require one language flag to describe application code, infrastructure and documentation together.

Proposed commands, not yet implemented:

```bash
pah init --dry-run
pah init
pah init --profile python --profile terraform
pah init --config-template ./team-harness.json
```

The dry run inspects allowed project metadata and shows detected profiles, task proposals, missing prerequisites, proposed files and unresolved choices without writing or executing project code. Interactive initialization presents the same proposal for review before writing. A template is validated local data, not executable configuration; do not fetch remote templates implicitly.

For a new manifest, precedence is explicit options, then supplied template, then discovered values, then defaults. Resolve scalar values accordingly, but explain conflicts and make array/map semantics explicit: repeated explicit profile options select the profile set; task definitions are merged by name with the higher-precedence definition replacing that task as a whole. Never append conflicting argv arrays or silently discard explicit user instructions. Enforced path/credential restrictions remain in force regardless of precedence.

For an existing manifest, validate and preserve it. Re-running init must not replace user-owned configuration through fresh discovery. Display any suggested additions as a separately reviewable change; apply them only through an explicit initialization/update decision with conflict detection. Configuration-file migration is explicit, versioned and tested.

First tested discovery support is Python/uv and Node, including actual configured package scripts. Maven, Terraform and other conventional metadata may be recognized as hints, but do not claim automated working tasks until their detectors/profiles are implemented and tested. Explicit profiles/tasks support installed toolchains independently of automatic discovery; profile names must resolve to a supported definition or produce an actionable unsupported-profile message.

Keep discovery bounded to the selected project root and allowed paths. Inspect files as data, not by executing build scripts/configuration. Init never installs toolchains, runs tasks/hooks, calls inference providers or imports/enables remote plugins. A noninteractive workflow can use a reviewed local template or explicit options, but must refuse unresolved conflicts rather than invent answers.

## Model and instruction profiles

Built-in adapters: fake, Ollama, OpenAI, Anthropic. Hosted profiles add a `credential_env` name and adapter-validated settings. Do not store credential values. Recognize adapter-specific options explicitly rather than pass arbitrary unvalidated settings through to SDKs.

An explicit CLI profile selection overrides the project default for that operation and is recorded. Per-project instructions and configured tooling take priority over defaults for gaps; surface contradictions rather than silently choose among conflicting explicit standards. Workspace restrictions are enforced code, not overridable prompt guidance.

A template choice is a versioned pack/template reference, distinct from choosing a model. Planning, implementation proposal and review templates share context/contracts but have different expected responses. Record project overrides and versions/hashes in the run evidence. Swapping a provider cannot change task definitions or permission rules.

## Feature contract

Feature IDs remain stable; changing a specification changes its hash and requires evidence against the current specification. Cross-repo features link component specs without granting each component access to every sibling directory. Existing Markdown can be explicitly selected with small accompanying metadata; no mandatory external spec framework.

```json
{
  "schema_version": 1,
  "id": "WEB-001",
  "title": "Reset the sample order scenario",
  "outcome": "A visitor can restore the sample journey without contacting the live API.",
  "context": [
    "src",
    "docs/product.md",
    "features/WEB-001/spec.md"
  ],
  "constraints": [
    "No live API calls in sample mode",
    "Do not modify live order state"
  ],
  "acceptance": [
    {
      "id": "AC-1",
      "description": "Reset restores the documented fixture state.",
      "tasks": [
        "test"
      ],
      "manual_review": true
    },
    {
      "id": "AC-2",
      "description": "Reset works with live API traffic blocked.",
      "tasks": [
        "test"
      ],
      "manual_review": true
    }
  ],
  "checks": [
    "lint",
    "types",
    "test",
    "build"
  ],
  "related_features": []
}
```

A task reference is evidence selection, not proof that the task tests that criterion. Record which checks ran and require review of their relevance. Criteria needing human review remain pending until explicitly recorded. AI output cannot set a criterion to verified. Feature acceptance refers to an exact specification and working-tree/report identity; later edits make that acceptance historical, not automatically current.

## Proposed command groups

These commands are design names to implement incrementally. Do not advertise or list unimplemented commands as working in help/docs.

| Group | Proposed commands | Boundary |
|---|---|---|
| Setup/identity | `pah init`, `doctor`, `--version`, `version` | Init previews changes and preserves existing files; doctor reports actual prerequisites |
| Features | `pah feature new ID`, `feature validate ID`, `feature accept ID` | Templates/schema and explicit human acceptance; no inferred completion |
| Inspection | `pah status`, `read PATH`, `search QUERY`, `diff` | Bounded workspace operations, no implicit model/network call |
| Context | `pah context --feature ID`; `context --task TEXT` | Preview/export selected instructions and content under limits |
| AI preparation | `pah plan --feature ID --profile NAME`; `propose --feature ID --profile NAME`; `ask --task TEXT --profile NAME` | Explicit model calls; plan/ask do not edit, propose produces a validated local change set |
| Apply | `pah apply CHANGESET_ID` | Preview and explicit local approval bound to proposal; revalidate paths/file state before writes |
| Execute | `pah run TASK --dry-run`; `run TASK`; `check --feature ID`; `report` | Reviewed argv tasks and genuine task outcomes, independent of AI |
| Services | `pah dev start TASK`, `dev status`, `dev stop RUN_ID` | Dedicated lifecycle with startup deadline and ownership checks; short-task timeout does not kill a healthy running service |
| Review | `pah review --feature ID --profile NAME` | Read-only AI findings based on selected diff/specification; does not override task results |
| Git checkpoint | `pah checkpoint --dry-run`; explicit interactive checkpoint | Preview intended files and existing staging; no automatic push/reset/stash |
| Packs/integrations | `pah upgrade --to VERSION --dry-run`, `remove --dry-run`, `adapter export` | Pack ownership and deliberate compatible upgrade, not in-place self-update of the CLI |
| Documentation | `pah docs pull`; `docs sync --feature ID --dry-run`; `docs sync --accepted --dry-run` | Pull verifies pinned bundle; sync proposes eligible documentation changes |
| MCP | `pah mcp serve` | Optional local read-only stdio server; model supplied by client |

Noninteractive mutation without a valid explicit approval mechanism is denied in the initial design. Do not expose a model-settable approval Boolean. Cached approvals become invalid when the proposal/source state changes. A user can invoke one operation at a time; a convenience workflow may orchestrate these later without changing boundaries.

### Result conventions

CLI exit categories: 0 operation succeeded; 1 executed required checks failed; 2 invalid usage/configuration; 3 policy denial; 4 dependency/provider unavailable. Timeouts/partial applies/provider errors carry structured reason codes and nonzero results. Preserve subprocess exit codes in task results even when the harness uses an aggregate exit category.

Reports distinguish PASS, FAIL, SKIPPED, NOT_CONFIGURED and PENDING human review. A successful context export or model response is not feature completion. A missing report is reported as missing. Sanitized published summaries exclude secrets/raw context; local detailed evidence remains ignored and bounded.

## Configurable feature documentation

Documentation is derived from accepted evidence, not a model claiming it has implemented a feature. An approved specification is planned work; accepted implementation is delivered work. Static command/schema references are generated independently from their code sources.

| Mode | Behaviour |
|---|---|
| `off` | No automatic feature-doc proposals or updates. Explicit invocation reports disabled mode unless the user deliberately overrides it. Evidence remains recorded locally. |
| `suggest` — default | After feature checks/review, propose factual docs/changelog changes for review, without applying them automatically. |
| `update` | Prepare documentation as a phase of the feature workflow; apply only through the same explicit reviewed change-set mechanism. No autonomous publication or commits. |

Generate a deterministic feature summary from spec ID/title, acceptance/evidence and source version when no model is configured. AI-assisted narrative elaboration is separately selected, uses an optional profile and remains proposed until reviewed. Never require a paid provider to write feature summaries.

For update mode, sequence code proposal/apply → checks/review → proposed feature-doc changes → apply/review/check relevant docs → explicit acceptance of the combined final state. Until acceptance, summaries are labelled pending; do not prematurely publish them as completed. Final metadata must not require a self-referential hash or a commit SHA that does not exist yet; use the prior evidence/source identity and record final acceptance separately.

With off/suggest modes, accept implementation based on actual evidence and leave documentation work explicit/pending. Catch-up is a deliberate `docs sync --accepted --dry-run` action against available accepted feature records. Re-enabling the setting does not trigger inference, writes or publication. If off-mode history was local and has been lost, explain the gap and request a reviewed source of truth; do not invent history from commit titles.

Managed feature summaries live under the configured directory with feature/source IDs; duplicate sync is idempotent for unchanged evidence. Preserve human-edited text through owned sections/conflict detection. A changelog edit is proposed with explicit scope, not a silent rewrite. Architectural reasoning/runbooks always require human review. Documentation paths share workspace/secret restrictions and read-only MCP cannot apply updates.

## Section 2 acceptance and next work

Review configuration defaults, provider/network boundaries, feature-to-evidence mapping, documentation toggle/catch-up and the difference between short tasks and development services. Examples above parse as JSON; they have not passed an implemented harness schema, since none exists yet. When implemented, test them as shared fixtures through Pydantic validation and generated-schema validation, plus deliberate invalid/denied cases.

This documentation section passes after review/merge, not after execution of the proposed commands. Step 03B's next section covers RelayCart service/data/security/deployment contracts and initial decision records. Step 03C reviews the complete design/checkpoint records before Step 04 code begins.
