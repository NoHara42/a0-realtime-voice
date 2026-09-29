# Release decision — 0.1.2

Mode: `local-loop` (source and package publication; no production deployment).
Decision date: 2026-09-29. Release steward: Codex. Release/support owner: NoHara42.
Candidate: annotated tag `v0.1.2`, with the source tree used by the checks below.
QA gate: **pass** for the scoped offline regression and package checks.
Authorization: owner explicitly requested release, changelog adaptation, commit
and push after the audit disclosed that live voice testing remained outstanding.

## Evidence

- Unit/regression and browser-store harness: 20 JavaScript tests passed.
- Integration with the Agent Zero framework: 43 pytest tests passed in `a0-rtv-dev`.
- Packaging and security: `scripts/package.py`, `scripts/check_release.py`, Python
  syntax checks and `git diff --check` passed. Runtime dependencies unchanged.
- Repository rulesets: none; no repository CI workflows or required check runs
  were present. Local checks supply this patch's verification evidence.
- Release notes: [RELEASE_NOTES.md](RELEASE_NOTES.md).
- Documentation sync: completed in [CHANGELOG.md](../CHANGELOG.md),
  [SECURITY.md](../SECURITY.md) and [SUBMISSION.md](../SUBMISSION.md).
- Behavior/spec sync: completed by regression tests for the audited failures.

## Explicit limits

| Artifact | Disposition | Owner / follow-up |
| --- | --- | --- |
| Fresh live end-to-end voice test | Waived for this source patch publication under the owner's release instruction following the disclosed audit limits | NoHara42; before production rollout |
| Production on-call/alert setup | Not applicable to a community ZIP/source release; no running user instance is changed | Installer/operator; at deployment |
| New dependency vulnerability scan | No dependency changes; package credential/artifact scan passed, not a full vulnerability scan | NoHara42; next dependency update |

## Operational handoff and rollback

After installing, end active calls and reload browser tabs. Check connection,
delegation/result narration, cancellation and chat switching in the target runtime.
If those regress, end calls and disable the plugin through plugin management.
If rollback is necessary, install the `v0.1.1` ZIP from the prior GitHub release
and reload; that version lacks these security fixes, so leaving voice disabled is
preferable until a corrected release is available. No schema/config migration or
data rollback is needed. Verify the normal Agent Zero chat still works and that
disabled voice controls disappear after reload.
