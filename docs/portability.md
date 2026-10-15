# Operating-system portability and acceptance

Decision: Windows, macOS and Linux are required for the first release.
Status: implementation prepared; native Windows/macOS CI results pending.
This is a development correction, not a stable release announcement.

## Shared behavior and native boundaries

The CLI and future MCP adapter call the same policy/core services. Configuration,
reviewed task plans, approval rules, output/time budgets, task outcomes and JSON
reports use the same contracts. Tasks invoke tools installed on the user's host;
portability does not make a Linux-only third-party tool work on Windows.

| Boundary | macOS/Linux | Windows |
| --- | --- | --- |
| Task launch | New POSIX session/process group | Waiting isolated Python launcher assigned to a Job Object before release |
| Descendants | TERM grace, then KILL; state check after denied signaling | Job termination, bounded active-process verification; kill-on-close fallback |
| Pipe capture | Nonblocking selector | Two readers, bounded queue and shared retained-output cap |
| Init/publication | Pinned directory FDs; exclusive temp and non-replacing link | Pinned directory handles denying delete sharing; exclusive temp and non-replacing rename |
| Link protection | No-follow operations | Reparse/junction rejection; hard-linked metadata rejected |
| New private files | POSIX mode 0600 | Protected current-user/LocalSystem DACL |

The Windows launcher uses the harness's CPython interpreter in isolated mode.
It cannot start project code until assignment succeeds. Assignment denied by a
restricted/nested job environment is a failure, not permission to run uncontained.
The launcher is an implementation detail, not another installed runtime.
Native Job Objects follow Microsoft’s documented descendant semantics; they are
not a general security sandbox. POSIX tools can deliberately detach; reviewed
programs retain user privileges and network/filesystem access on all platforms.

Mac regression: a parent can exit before group cleanup completes. The old second
signal could raise PermissionError and crash the check. The correction waits,
checks for disappearance, and uses a bounded process-state snapshot after denied
signaling. Only absent or zombie-only groups are accepted by that fallback.
Live or unknown state yields CLEANUP_UNCONFIRMED and FAIL. Permission errors are
not silently swallowed, and the original regression remains an acceptance test.

Relative manifest paths use forward slashes on all hosts. Drive paths, traversal,
Windows device names, alternate data streams and unsafe filename characters are
denied consistently. Absolute task executable paths are permitted in argv.
The baseline is local filesystems: NTFS on Windows and standard local filesystems
on macOS/Linux. UNC shares are rejected. New files get private permissions;
existing user directories/ACLs are not silently rewritten. Use a user-owned
workspace. Windows symbolic-link development tests require the runner's symlink
privilege; ordinary harness use does not require administrator permissions.

Standard npm.cmd is invoked through its adjacent npm-cli.js and node.exe. Generic
.cmd/.bat shims are refused instead of implicitly interpreting shell metacharacters.
Other managers/tools can configure an explicit executable/interpreter. Deliberately
configured shells are project code and must be reviewed as such.

## Evidence and release gate

The workflow `.github/workflows/portability.yml` runs on pull requests, pushes to
main/current Step 04C branch, and manual dispatch. It uses hosted Windows, macOS
and Linux runners with CPython 3.12, pinned action commits, read-only repository
permissions, no persisted checkout credentials, a pinned uv version, and locked
project dependencies. It runs lint/format, unit and process integration tests,
build, installed-wheel smoke outside checkout and harness self-check. No secrets,
package publication, deployment or version increment is required.

| Evidence | Current status |
| --- | --- |
| Linux preparation run | 164 passed, 7 native Windows tests skipped; not Windows evidence |
| Adrian's Mac run before correction | 133 passed, 1 cleanup failure; build correctly skipped |
| Adrian's Mac corrected run | Pending |
| Hosted Linux acceptance | Pending |
| Hosted macOS acceptance | Pending |
| Hosted Windows acceptance | Pending |

Windows-native tests cover assignment refusal before project execution, descendant
cleanup across a new process group, junction refusal, directory pinning,
create-only init races, hard-linked reads and protected report ACLs. The ordinary
execution/init/report tests also run on Windows. Only POSIX signaling tests skip
there; native Windows tests skip on other systems. Shared pipe-bound tests execute
on every host. A skipped native test on Linux is never proof of Windows support.

Do not merge the Step 04C PR until the corrected local checks and all three CI
jobs pass. Record run links, source commit and actual results in progress/checkpoints.md.
The CI can run after committing/pushing the branch, before merging it.
Broader release/security CI is still Step 04D. This workflow brings the portability
acceptance portion forward so Windows is not deferred beyond the first release.

## Standards and source references

- [Python subprocess: security and Windows argument behavior](https://docs.python.org/3/library/subprocess.html#security-considerations)
- [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
- [Microsoft nested jobs](https://learn.microsoft.com/en-us/windows/win32/procthread/nested-jobs)
- [Microsoft CreateFileW: sharing and reparse points](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)

Scope: these sources inform native implementation choices. Actual compatibility
claims come from recorded test results, not from documentation alone.
