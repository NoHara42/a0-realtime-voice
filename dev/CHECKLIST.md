# Realtime Voice plugin: plan and checklist

Working file for building the plugin. Not shipped (the `dev/` directory is
excluded from the release ZIP).

## Findings from the Agent Zero v2.13 source

- Plugins are discovered by `plugin.yaml`. Custom plugins live in
  `/a0/usr/plugins/<name>/` and import themselves as `usr.plugins.<name>...`.
  Community names match `^[a-z0-9_]+$` and have no leading `_`.
- API handlers in `api/*.py` subclass `helpers.api.ApiHandler` and are served at
  `POST /api/plugins/<name>/<handler>` with auth and CSRF on by default. They are
  resolved per request, so no restart is needed.
- WebUI hooks go in `extensions/webui/<breakpoint>/`. The existing voice mode is
  two bundled plugins: `_whisper_stt` (mic button teleported into
  `#chat-buttons-wrapper` from `chat-input-box-end`, plus a card in
  `voice-settings-main`) and `_kokoro_tts` (a TTS provider). Both register with
  `/js/stt-service.js` and `/js/tts-service.js`.
- Settings: provider API keys are dotenv `API_KEY_<PROVIDER>` values edited in
  Settings and read with `models.get_api_key("openai")`. Plugin options come from
  `default_config.yaml` plus `webui/config.html`, read with
  `helpers.plugins.get_plugin_config(name, agent=...)`, which respects
  project and profile scope.
- Sending a message to the agent: `mq.log_user_message(...)` shows it in the
  chat, then `context.communicate(UserMessage(...))` returns a `DeferredTask`,
  and `await task.result()` gives the final `response` text. `api/message.py`
  already does exactly this synchronously.
  `UserMessage.system_message` is the supported way to attach framework hints
  without changing the text the user sees.
- When the context is already running, `communicate()` turns the message into
  an intervention on the running task and returns that same task.

## Design decisions

1. **Transport.** The browser uses WebRTC straight to OpenAI and the SDP goes
   through the Agent Zero backend (OpenAI's "unified interface",
   `POST /v1/realtime/calls`). The browser never holds any credential, not even
   an ephemeral one. The backend writes the session config (instructions, tool,
   voice, VAD), and the answer carries a `call_id` that we could use later for a
   sideband socket. Media flows peer to peer, so latency matches the
   ephemeral-key flow.
2. **Tool routing.** Function calls arrive on the `oai-events` data channel in
   the browser, which forwards them to `POST /api/plugins/realtime_voice/delegate`.
   That handler runs the same code path as `/message`, so the delegated task shows
   up in the open chat like a typed message, with full progress visible.
3. **Acknowledgement.** The tool description tells the model to call the tool
   right away. On the call, the client immediately sends
   `response.create` with per-response instructions ("say briefly that you
   handed it off"). This is deterministic, not left to prompting. The model keeps
   talking while the call is pending (Realtime supports async function calls).
   Live verification required an out-of-band acknowledgement with empty input;
   otherwise the model sometimes guessed the task answer in its acknowledgement.
   When the result arrives, the client sends `function_call_output` plus
   `response.create`, queued until no response is active.
4. **Concurrency.** One in-flight voice delegation per context. A second call
   while the agent works is passed to it as an intervention and returns
   immediately with "added to the running task".
5. **Coexistence.** The plugin is separate and does not modify
   `_whisper_stt` or `_kokoro_tts`. While a realtime session is live it stops
   the TTS service whenever it starts, so Agent Zero doesn't read replies aloud
   twice, and it stops Whisper recording.

## Checklist

### Backend
- [x] `plugin.yaml`, `default_config.yaml`, `.gitignore`, `LICENSE`
- [x] `helpers/config.py`: normalize and validate config
- [x] `helpers/session.py`: build the session config and create the WebRTC call (SDP proxy)
- [x] `helpers/delegation.py`: delegate a task to the agent context, with in-flight tracking and result trimming
- [x] prompts: realtime instructions and the agent-side voice hint
- [x] `api/status.py`, `api/session.py`, `api/delegate.py`

### Frontend
- [x] `webui/realtime-voice-store.js`: WebRTC session, event handling, delegation, interruption, mute, captions
- [x] composer button (`chat-input-box-end`), voice overlay panel
- [x] Settings > Voice card (`voice-settings-main`), `webui/config.html`
- [x] coexistence with the TTS and STT services (implemented; physical-device listening remains manual)

### Verification
- [x] pytest (offline): config, session builder, SDP proxy request, delegation (stubbed `communicate`)
- [x] `scripts/wav_smoke.py`: live Realtime over WebSocket with the same session builder, WAV in, delegation through the real helper in a standalone AgentContext, audio and transcript out
- [x] disposable dev container (port 50090, isolated `usr/`) with the plugin mounted
- [x] headless-Chromium end-to-end test: fake mic from a WAV, real UI button, WebRTC, delegation, spoken result; actual RTP barge-in and manual interrupt
- [x] install through the plugin installer (ZIP), toggle, uninstall, and leave no leftovers (separate packaging container; never uninstall the bind-mounted source)
- [x] install into the user's instance (`agent-zero-v2`) via authenticated HTTP ZIP API and enable; confirmed configured key and model, no restart

### Docs and community prep
- [x] README: setup, architecture, limitations, manual browser test steps
- [x] draft Index entry `dev/index.yaml.example` (not submitted; public repository URL and current tag validation still required before publication)
- [x] verification report: `dev/VERIFICATION.md`

## Remaining human checks / intentionally out of scope

- Physical microphone/speaker quality, room echo, subjective latency, Safari/mobile,
  remote HTTPS/reverse-proxy behavior, and long-duration sessions.
- Public repository creation and community-index submission were not requested.

## 0.1.1 polish and submission preparation

- [x] Inactive headset contrast and visible keyboard focus, dark and light themes.
- [x] Native text input styling for all settings fields.
- [x] Security review, safe provider-error handling, input limits, stale-context rejection.
- [x] 42 Python tests, 11 JS tests, browser style checks, real HTTP auth/CSRF checks.
- [x] SECURITY.md, CHANGELOG.md, SUBMISSION.md, recommended index tags.
- [x] Allowlisted release ZIP plus source/archive credential-pattern and artifact audit.
- [x] Install reviewed changes into running instance, preserving configuration.
- [x] Review report: `dev/SECURITY_REVIEW.md`.
- [x] Publish source to `NoHara42/a0-realtime-voice` and release `v0.1.1` with ZIP.
- [x] Clone the index fork into `~/Git/a0-plugins`, prepare and push the entry.
- [x] Download current index and pass upstream submission validation.
- [ ] Owner approval of the proposed PR title/body/diff, then open upstream PR.
