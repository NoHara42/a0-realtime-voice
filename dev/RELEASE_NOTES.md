Realtime Voice 0.1.2 fixes task-dispatch, error-handling, and chat-startup issues found during the maintainer audit.

## Fixes

- Escape error messages before displaying them in Agent Zero's HTML notifications.
- Only dispatch completed tool calls from completed Realtime responses. Cancelled, failed, or incomplete responses cannot start agent work.
- Prevent queued delegation from starting after End call.
- Keep backend error bodies and submission exceptions out of results sent to the voice model.
- Abort voice startup if the selected chat changes while chat creation is pending.
- Apply completion checks and safe delegation errors to the WAV smoke-test utility.

## Verification

- 20 JavaScript tests passed, including cancellation, notification escaping, and startup regressions.
- 43 Python tests passed in the Agent Zero development container.
- Installable ZIP passed source matching, metadata, and credential/artifact checks.
- Live OpenAI/WebRTC and physical microphone testing were not rerun for this patch.

## Update

Install the attached `realtime_voice.zip` through Agent Zero's plugin installer, or update from this repository using the Git installer. End existing calls and reload browser tabs after updating. No configuration or data migration is required.

Ending a call still leaves already-dispatched Agent Zero tasks running; use the normal agent stop control to stop them.
