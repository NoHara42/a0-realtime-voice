# Release decision — 0.1.3

Mode: `local-loop` (source/package publication; no production deployment).
Decision date: 2026-09-29. Release steward: Codex delegated follow-up agent.
Release/support owner: NoHara42. Candidate: annotated tag `v0.1.3`.
QA gate: **pass** for the scoped offline regression and package checks.
Authorization: owner requested a delegated audit follow-up, fixes and release.

## Evidence

- Unit/browser harness: 20 JavaScript tests passed.
- Agent Zero framework integration: 49 Python tests passed, including execution
  reuse, overlapping cleanup, request cancellation and setup-error regressions.
- Source-matched ZIP, metadata and credential/artifact checks passed.
- Python syntax and `git diff --check` passed; runtime dependencies unchanged.
- No repository CI workflows, required checks or code-owner approval rules.
- Change communication: [release notes](RELEASE_NOTES.md), [changelog](../CHANGELOG.md).
- Documentation sync completed in changelog, submission and publication notes.
- Behavior/spec sync completed through regression tests for the audited failures.

## Explicit limits and follow-up

| Artifact | Disposition | Owner / follow-up |
| --- | --- | --- |
| Live end-to-end voice/authenticated HTTP tests | Waived for this source patch under the owner's release instruction following disclosed limits | NoHara42; before production rollout |
| Production monitoring/on-call | No running instance changed by source publication | Installer/operator; at deployment |
| Dependency vulnerability scan | No dependencies changed; credential-pattern checks run, not a specialist scan | NoHara42; next dependency update |
| Historical personal metadata | Forward-only cleanup; old commits and release records remain unchanged | NoHara42; separate coordinated history-rewrite plan |

Agent Zero currently exposes execution identity only through DeferredTask's
`_future`; the helper captures this handle once and fails safely if the expected
future is unavailable. Recheck compatibility when upgrading the framework.

## Handoff and rollback

After installing, reload tabs and check voice connection, two successive tasks,
result narration and interruption. If results are missing or setup regresses,
end calls and disable the plugin. Roll back to the v0.1.2 ZIP only if necessary;
it still has the task-reuse issue, so disabling voice is preferable until fixed.
No data/config migration or reversal is needed. Verify normal chat still works
and voice controls disappear when disabled. No live installation is modified.
