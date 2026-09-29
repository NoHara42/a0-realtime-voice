# Changelog

## 0.1.3 — 2026-09-29

- Track delegation by execution future so a reused Agent Zero task wrapper cannot
  lose a new result or clear the new execution's tracking.
- Keep HTTP request cancellation from cancelling an already dispatched agent task.
- Sanitize errors from chat lookup and configuration as well as task submission.
- Add regression coverage for task reuse, cancellation, and setup failures.
- Remove local home-directory paths from the current publication notes. Historical
  commit metadata is unchanged; new release commits use a GitHub noreply identity.

## 0.1.2 — 2026-09-29

- Escape error text before sending it to Agent Zero's HTML notifications.
- Dispatch only completed tool calls from completed Realtime responses; suppress
  queued dispatch after ending a call.
- Keep delegation HTTP errors and submission exceptions out of voice results.
- Abort voice startup if the user switches chats while chat creation is pending.
- Add regression tests for cancellation, error handling, and startup races.

## 0.1.1 — 2026-09-24

- Increase inactive headset-button contrast using Agent Zero theme colors and add
  a visible keyboard focus outline.
- Use native text input types so all plugin settings inherit Agent Zero styling.
- Reject malformed/oversized session and delegation requests before dispatch.
- Reject deleted session contexts instead of falling back to global settings.
- Keep provider exception text out of session responses/logs and voice failure
  summaries; add regression coverage for credential/HTML disclosure.
- Add security model, submission instructions, and release-package checks.

## 0.1.0 — 2026-09-24

- Browser-to-OpenAI WebRTC speech-to-speech with server-side session setup.
- Normal Agent Zero task delegation, isolated spoken acknowledgement, result
  narration, natural interruption, captions, mute, and call cleanup.
- Plugin settings, offline tests, and a live WAV smoke-test script.
