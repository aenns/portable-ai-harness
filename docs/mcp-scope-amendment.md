# MCP capability parity — approved scope amendment

Decision date: 11 October 2026
Recorded: 15 October 2026
Status: approved design; implementation and client compatibility not yet demonstrated.

## Decision and precedence

Implement and validate the CLI first. Then expose the same supported application capabilities through a thin optional local stdio MCP adapter over the same core services. This supersedes the read-only-only first-release restriction in the Step 03 documents; Step 03's completed review remains historical evidence. The first stable release targets core capability parity for at least one documented, tested client using a supported approval path. Do not silently redefine partial delivery as full parity; any release-scope reduction is a separate reviewed decision.

CLI and MCP map inputs/results to common validated contracts and call shared application services. MCP does not spawn the CLI and parse terminal output. The core contains configuration, policy, context, feature workflows, provider adapters, patches, task execution, review, reporting and Git checkpoint behavior. Terminal prompts/rendering and MCP transport/tool schemas are adapter concerns. Terminal-specific flags, display controls and manual installation commands need not be mirrored one-for-one as tools; the capability matrix explains how their underlying workflows are supported.

## Capability target

| Capability | MCP target / constraints |
|---|---|
| Inspect/context/docs retrieval | Shared bounded paths, secret denials and selected context; verified pinned documentation bundles |
| Init/configuration/managed packs | Preview changes and explicit approval for writes, conflicts and version upgrades; no automatic toolchain/plugin installation |
| Feature/plan/propose/ask/review | Shared specifications, instructions, provider profiles and structured outputs; external calls require explicit selection and disclosure |
| Apply source/tests/docs | Reviewed change set; approval bound to exact changes and relevant source state; revalidate before applying |
| Run/build/test/check/report | Reviewed named argv tasks with cwd, budgets and actual results; no raw model-supplied shell commands |
| Development lifecycle | Owned start/status/stop with bounded startup, process ownership and tested disconnect/recovery behavior |
| Git checkpoints | Show intended files, staged state and hook side effects; commit only approved content; no implicit push/reset/stash/discard |
| Version/doctor/capabilities | Truthful installed versions, local readiness, effective policy and supported client capabilities |

The client normally supplies conversational inference. Direct-provider calls are optional explicit operations using configured credentials; MCP does not share subscriptions between providers or supply a model. No remote/network MCP server, autonomous repair loop or hosted harness service is added by this amendment.

## Approval and policy boundary

A request received from an assistant is not proof of human approval. Read-only remains the default tool profile; a reviewed-capabilities profile is opt-in and activates only implemented capabilities supported by the effective policy and tested approval path. Selecting the profile or accepting a client's generic connection prompt does not authorize every later operation.

Consequential operations first return a reviewable proposal describing action, repository/workspace, file diff or named task/argv/cwd, relevant configuration/source identity, declared side effects, selected provider/network destination and limits. A trusted local human approval mechanism or a verified client-mediated approval channel authorizes that exact proposal. The detailed interaction/protocol is an implementation checkpoint, not assumed merely because a client supports MCP. A separate local approval interaction may be required in clients that cannot safely carry the approval themselves.

Approval grants are scoped, short-lived and single-use for the approved operation; changed proposals or relevant state invalidate them. Do not accept an `approved: true` argument, a model-authored confirmation message or a token minted by an unrestricted MCP tool as human consent. The model cannot manufacture, broaden or replay approval grants. Recheck current policy, workspace paths, source state and process ownership at execution. Bound cancellation/retry behavior and recover without applying a second side effect after a disconnect or duplicate request.

If the required approval mechanism is unavailable, the action is denied and the client is labelled partial/read-only. Failures are explicit; no silent fallback to another provider, shell command or weaker policy. External assistants can still use their own native tools outside this boundary; harness safeguards are not an OS sandbox or control of the whole IDE.

## Configuration and compatibility

The configuration example keeps mcp.enabled false and tool_set read-only as the conservative default. The design adds an opt-in reviewed tool-set profile; its schema and exact settings become authoritative only when implemented and tested. Configuration validation rejects unknown values; changing a string cannot activate unimplemented tools or bypass approval. Expose requested versus effective capability status and reasons for denial.

Publish a versioned CLI-to-MCP capability matrix with: core operation, tool equivalent, effects, approval requirement, supported profile/client/version and test evidence. Unsupported/untested integrations are labelled as such. The core model adapters and the MCP client/model are different compatibility dimensions.

## Implementation order and acceptance

1. Step 04A: installable CLI core, help/version and meaningful unit tests. No MCP implementation is required in this section.
2. Build configuration, inspection, task/check and feature/model/change workflows through the CLI, including their safety tests and documentation. Use the harness during development once usable.
3. Add the local MCP adapter and structured results without duplicating the core. Start read-only, then add each reviewed capability after its CLI behavior and approval mechanism pass tests.
4. Test corresponding CLI/MCP results and policy decisions against shared fixtures. Record intentional presentation differences, real-client workflows and unsupported cases.
5. Demonstrate denied/forged/expired/stale/replayed approvals, secret/path denial, task timeout/output limits, failed checks, Git staged-state preservation, hook side effects and cancellation/disconnect behavior. Logs go to stderr, not protocol stdout.
6. Validate at least one real supported client across the claimed operation matrix, including the documented trusted approval route for writes/execution/commits. Dogfood source-and-test implementation plus validation through both interfaces before claiming parity or promoting stable.

Keep release/launch gates, free-hosting decisions and application boundaries unchanged. Record feedback and pin deliberate candidate upgrades. Passing this design amendment does not establish any working code, client compatibility or security test result.
