# Local verification — 2026-09-24

Runtime: `agent0ai/agent-zero:latest`, actual container source revision
`b1cbd1f9` (UI labels itself v2.12). Reference source in `../a0-ref` describes
v2.13; no Agent Zero core files were modified.

## Offline

- `node --test tests/js/*.mjs`: 11 passing, including acknowledgement sequencing,
  pending results during speech, response races/errors, malformed tools,
  interruptions, caption bounds, and late results after closing.
- Framework pytest: 30 passing. Configuration, session construction, mocked SDP exchange and
  errors, normal delegation, interventions, cancellation, result trimming,
  authenticated/CSRF endpoint defaults, missing keys, disabled sessions,
  network errors, deleted-chat rejection, and the task-completion race.
- ZIP created from a source allowlist by `scripts/package.py`; excludes credentials,
  runtime configuration, toggles, caches, dev artifacts, and Git metadata.

## Live OpenAI / real Agent Zero

`dev/browser-live.mjs`, headless Chromium with a synthetic WAV microphone:

1. Clicked actual Realtime voice button and established a real WebRTC call.
2. OpenAI transcribed “Please use the terminal to calculate 17 times 23…”
3. Received `delegate_to_agent`; heard transcript “On it. Agent Zero is working
   on it now.” in a separate acknowledgement response.
4. Normal Agent Zero ran a terminal calculation and returned 391 through the
   authenticated plugin delegate endpoint.
5. Realtime spoke “391. Computed via the terminal.” after the function output.
   Received 38,613 inbound audio bytes; no Realtime error events in the task flow.
6. Started a long spoken story; Interrupt caused `output_audio_buffer.cleared`.
7. Started another long story; injected actual audio into the WebRTC sender.
   Verified `input_audio_buffer.speech_started` and playback clear (barge-in).
8. Verified mute/unmute and closed peer connection on End call. The earlier
   unmodified-microphone test also checked the actual track's `enabled` flag.

The real task agent in the disposable instance used OpenAI `gpt-4.1-mini` directly.
The live user's existing task model configuration was preserved.

`scripts/wav_smoke.py` also passed with live OpenAI over WebSocket, real terminal
delegation, an acknowledgement, final transcript “The answer is 391,” and a
24 kHz PCM16 output WAV. It needs Docker runtime initialization; this was added
after the first attempt incorrectly selected Agent Zero's development RPC path.

## Packaging and UI

- Installed ZIP in isolated `a0-rtv-package-test` using normal installer helper.
- Enabled through the framework API; headset button appeared.
- Opened the actual plugin settings modal, changed voice to cedar and clicked
  Save; status API returned cedar.
- Disabled through API and reloaded: headset absent, original mic still present.
- Uninstalled through normal plugin management HTTP API; confirmed the installed
  plugin directory no longer existed. Only that disposable installation was removed;
  source and release ZIP remain available.
- Installed final ZIP into `agent-zero-v2` using its authenticated HTTP installer,
  enabled via plugin management API, confirmed enabled/key-present/model status.
  No user instance restart or task model configuration changes.
- Removed the temporary OpenAI key copy from the dev instance and stopped both
  disposable test containers after verification. The user's configured key is
  untouched. Synthetic output audio is retained locally in `dev/out/reply.wav`.

## Findings worth preserving

- A normal-context acknowledgement sometimes guessed the easy task answer while
  the backend was still running. An out-of-band response with empty input fixed
  this in live tests. Tests now wait for the actual delegate response and the
  subsequent spoken result, rather than accepting matching speech alone.
- Agent Zero's model settings use presets now, and the default dev preset pointed
  at OpenRouter. Voice itself only contacts OpenAI; task models follow normal
  Agent Zero settings.
- Framework installation initially disables a newly installed plugin, so explicit
  enablement and a browser reload are part of setup.
- The test runtime emitted a LiteLLM logging-worker shutdown warning on some agent
  runs; terminal work and returned results succeeded.

## Not verified

Physical microphone/speaker quality, audible naturalness, subjective latency,
Safari/mobile, echo cancellation in a real room, long sessions, and remote proxy
timeouts. README provides exact manual steps. No publication or community PR.
