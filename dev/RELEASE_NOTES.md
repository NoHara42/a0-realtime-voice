Realtime Voice 0.1.3 addresses the remaining runtime findings from a separate maintainer audit.

## Fixes

- Track and await each Agent Zero execution independently, even when Agent Zero reuses its task wrapper. Finishing an older request can no longer remove tracking for a newer execution.
- Preserve already dispatched agent work when its HTTP waiter is cancelled.
- Return a fixed safe failure message when chat lookup or configuration setup fails, keeping framework tracebacks out of delegation responses.
- Remove unnecessary local home-directory paths from the current publication notes and use a GitHub noreply identity for this release's commit and tag.

The audit's cancelled/failed response dispatch and raw browser error forwarding findings were already fixed in v0.1.2. Existing Git history and older publication records still contain the previous personal metadata; this patch does not rewrite history.

## Verification

- 20 JavaScript tests passed, including the existing dispatch and error-disclosure regressions.
- 49 Python tests passed in the Agent Zero development runtime, including a reused framework task wrapper, overlapping waiter cleanup, request cancellation, and setup exceptions.
- Installable ZIP passed source matching, metadata, and credential/artifact checks.
- Live OpenAI/WebRTC, authenticated HTTP, and physical microphone tests were not rerun. Credential-pattern checks are not a comprehensive secret scan.

## Update

Install the attached `realtime_voice.zip` through Agent Zero's plugin installer, or update from this repository using the Git installer. End existing calls and reload browser tabs after updating. No configuration or data migration is required.

Ending a call leaves already dispatched Agent Zero tasks running; use the normal agent stop control to stop them.
