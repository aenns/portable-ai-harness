# Step 03A — Approved first-release scope

Scope version: 1
Decision date: 7 October 2026
Owner: Adrian Enns
Status: approved scope recorded and merged at commit 96cc799.

This checkpoint supplements the RelayCart Step-by-Step Build Guide. Where the guide still limits the harness to read-only model consultation or recommends promoting milestones immediately, this approved contract takes precedence. It adds reviewed direct-model patch application and defers stable promotion/public announcements until development use and portfolio readiness are validated. Application implementation has not started. The completed Step 03 design review is recorded separately in RelayCart's design checkpoint.

## Product purpose

Portable AI Harness helps a developer define a change, prepare bounded context, implement source and tests through a chosen coding assistant or configured model, run reviewed project tasks, and inspect evidence before accepting the work. It is an independent developer product. Application startup, build and runtime work without it.

The initial user is Adrian developing the harness and all six RelayCart repositories. External users can install it in existing projects and configure their own tasks, instructions and supported model profiles without modifying harness source.

## First-release contract

| Area | Included |
|---|---|
| Distribution | Pinned Python package, help/version information, isolated installation, explicit CLI version switching and ownership-safe managed-file removal |
| Project setup | Safe initialization, Python/uv and Node discovery, reviewed custom argument-array tasks for other installed toolchains, JSON Schema validation and truthful missing-tool reporting |
| Feature definition | Small feature template, acceptance criteria, plain-language requests and explicitly selected existing Markdown specifications; no mandatory external specification framework |
| Context | Bounded status/read/search/diff/context operations, selected source/docs/contracts, path restrictions and sensitive-file exclusions |
| Prompts and styles | Pinned planning/implementation/review templates, project overrides, project/organization standards and versioned defaults for gaps |
| AI profiles | Fake, Ollama and optional OpenAI/Anthropic adapters, capability checks, endpoint configuration where supported, environment references for credentials and no silent provider fallback |
| Token management | Input budgets, reserved instruction/output space, adapter-aware counting or labelled estimates, request preview and available actual usage reporting |
| Implementation | Existing coding assistant route plus direct-model reviewed patch route, including source files and tests |
| Execution | Named build/test/run/check tasks, bounded output/timeouts, process cleanup, explicit start/stop for long-running development servers |
| Review | Deterministic checks and separately labelled AI review against specification/conventions; human acceptance remains explicit |
| Git checkpoints | Inspect status before editing; configurable offer of an explicit local checkpoint commit, with reviewed file selection and preservation of existing changes |
| Integrations | Terminal baseline, tested VS Code workflow, supported Copilot instructions, and optional local read-only MCP bridge tested with one actual client |
| Evidence | Feature/run IDs, spec/context/prompt versions or hashes, source state, task outcomes and available model metadata, with structured redacted logs |
| Documentation | Installation, local build, tools/schema, examples, compatibility, architecture, decisions/tradeoffs, limitations, upgrade and troubleshooting guidance |

## Development workflow

Request or specification → inspect workspace and checkpoint decision → review plan/context → implement → run relevant checks → review diff/results → explicitly accept → commit and PR.

A small fix needs a lightweight request; a cross-service feature needs acceptance criteria, contract impacts and linked component work. The harness does not force every change through a large specification ceremony.

### Assistant-led route

Copilot, Cursor, ChatGPT, Claude or another selected tool supplies its supported AI/editing workflow. The harness supplies project instructions, bounded context and reviewed task/check tools. A tool without local filesystem/terminal access can use manual context export and a proposed patch, with extra manual steps. Do not promise native integration with every product/plan/version.

### Harness-led route

The selected direct provider returns a proposed patch. The harness previews changes and applies them only after explicit user approval. Validate allowed paths, expected file state, size limits and conflicts; refuse to overwrite intervening modifications. Define predictable failure/recovery behaviour before enabling writes. Proposed model text cannot invent executable commands. Only explicitly selected, reviewed named tasks run. Keep this a bounded workflow rather than an unattended repair loop.

## Instructions and security boundaries

Use explicit project/organization guidance, established repository conventions and configured tools, then documented default packs for gaps. Surface conflicts. Defaults are established engineering practices, not a claim of one universal coding style. Prompt instructions do not override enforced workspace or credential restrictions.

Do not automatically install or import remote plugins. Define versioned extension interfaces and configuration selection of installed compatible adapters. Publish accurate capabilities and installation prerequisites. An example separately packaged extension can follow the core release; a marketplace is outside scope.

Before implementation, inspect Git state and offer a checkpoint when policy calls for it. A checkpoint commits only reviewed intended files. Never silently stage everything, commit sensitive files, push, reset, stash or discard work. Record dirty state and preserve pre-existing work if the user chooses to continue. A checkpoint is recoverability evidence, not a substitute for backups or protection of ignored files.

For MCP v0.1.0, expose read-only inspection/context/documentation tools through local stdio, with shared limits and denials. No MCP source editing or task execution in the initial bridge. The client supplies its model and user interface; MCP is not a model, universal subscription bridge or replacement for host permissions. Operational logging goes to stderr, not protocol stdout.

## Dogfooding and improvement agreement

Once the core is usable, use the harness for most subsequent development in every repository, including infrastructure, documentation and contract changes. Bootstrap earlier work with direct commands. Named underlying commands remain documented and available if the harness is unavailable.

For each real feature, record: request/specification, harness and pack versions, relevant context/prompt, implementation route, named checks actually run, result and friction observed. Avoid storing raw private prompts, secrets or model context in public records.

At each feature/checkpoint, discuss what helped, what was awkward, whether anything surprising happened and one useful improvement. Classify feedback as a bug, usability/configuration improvement or scope extension. Fix safety/data-loss/correctness issues before resuming affected operations; prioritize routine improvements without repeatedly restarting the architecture.

Change the harness in its own repo and test fixtures. Build/pin an exact candidate version, validate in one consumer, then deliberately update the others. Never silently pull the newest harness into every project or change published artifacts. An application feature can proceed using documented direct commands if the harness fails, with the bypass reason recorded and a focused harness issue retained.

Before stable promotion, exercise installation and the feature-to-validation workflow outside the development checkout. Verify upgrades/conflicts/removal, intended source changes, tests, direct task execution without the harness and compatibility claims. Incorporate lessons from using the harness for real RelayCart work.

## Application scope and engineering evidence

One synthetic order scenario: create an order, trigger a supplier failure, recover without duplicate business effects and explain the incident using authorized evidence. Complete static sample mode and independently deployed API/AI live mode are separate, clearly labelled experiences.

Keep seven independent repositories: portable-ai-harness, relaycart-web, relaycart-api, relaycart-ai, relaycart-contracts, relaycart-infra and relaycart-docs. Show versioned interfaces, tenant/service authorization, durable retries, SQL transaction integrity, recoverable document projections, CI/CD, exact tested artifacts and rollback.

Use lightweight meaningful-boundary JSON logs, HTTP trace propagation and durable workflow correlation across retries. Sample mode has a local synthetic timeline and no remote telemetry. Optional aggregation/export failures must not break business functionality. Test one selected free-cloud profile and one compatible self-hosted profile; do not claim every cloud is free or universally tested.

## Release and communication sequencing

Use local/candidate packages and exact pinned versions while developing. Candidate publication and already-public source are allowed; they are not stable launch announcements. Do not advertise products as finished before validating them through actual development use.

Prepare documentation, case studies and communication assets throughout development. Promote the stable harness and launch the completed portfolio only after their acceptance gates and a coherent evidence pack are ready. Share a backlog of completed engineering work after launch, avoiding dependence on uninterrupted future development. No external posting or messaging is authorized by this checkpoint.

## Deferred

Unattended agents, multi-agent orchestration, MCP mutations/execution, plugin marketplace, hosted harness SaaS, real payment/logistics integrations, Kubernetes/service mesh and additional cloud implementations. Preserve useful extension boundaries without implementing these in the initial release.

## Step 03A acceptance

- Adrian has agreed this first-release scope in conversation: PASS.
- Code/test implementation routes, Git checkpoints, standards and read-only MCP boundary are explicit: PASS for design only.
- Dogfooding and controlled improvement/release policy are explicit: PASS for design only.
- Scope recorded, reviewed and merged into the Git repository: PASS (commit 96cc799).
- No implementation, compatibility test, release or deployment is claimed complete.

After this document is recorded in the harness repo, continue Step 03B: architecture, configuration/tool interfaces, acceptance specifications and ownership across repositories. Step 03C validates/merges the complete design checkpoint before Step 04 implementation.
