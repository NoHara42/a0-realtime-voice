# Realtime Voice for Agent Zero

Talk continuously with Agent Zero, interrupt replies, and hear the results of
delegated tasks. Adds a headset button beside the existing microphone. Requires
Agent Zero's plugin architecture (tested on Docker revision `b1cbd1f9`, showing
v2.12 in its UI), a
microphone, and an OpenAI account with Realtime API access and billing.

## Install and configure

1. In Agent Zero's **Plugins → Install → Git** flow, use
   `https://github.com/NoHara42/a0-realtime-voice`.
   Alternatively download `realtime_voice.zip` from the
   [GitHub releases](https://github.com/NoHara42/a0-realtime-voice/releases) and use
   **Plugins → Install → ZIP**, or build it with `python3 scripts/package.py`. The
   installed directory must be `usr/plugins/realtime_voice`.
2. Enable **Realtime Voice** in Plugins. Reload the browser after installation,
   toggling, updating, or uninstalling so WebUI extensions are refreshed.
3. Set the OpenAI key in **Settings → API Keys → OpenAI**. The plugin reuses the
   normal server-side key; there is no separate credential store.
4. Open **Realtime Voice → Configure** in Plugins or the Voice settings card.
   Set the Realtime model, voice, turn detection, and optional caption model.
   Defaults are `gpt-realtime-2.1`, `marin`, semantic VAD, and `gpt-transcribe`.
   Model availability depends on your OpenAI project; change the model if the API
   rejects it. Project and agent profile overrides use normal plugin settings.
5. Open Agent Zero at **localhost or HTTPS**. Browser microphone access will not
   work at a plain HTTP LAN address. Select a chat and click the headset button.

No additional runtime packages, voice servers, or third-party voice hosting are
installed. Delegation uses your normal Agent Zero model/tools. For a completely
OpenAI-only setup, select OpenAI providers in Agent Zero's model presets too;
existing presets may use other providers, and requested web tools may contact
other websites. Voice and task model usage are billed separately.

## How it works

The browser sends a WebRTC SDP offer to the authenticated plugin session endpoint.
Agent Zero attaches the configured instructions, tool, voice, and VAD settings,
then calls OpenAI's `/v1/realtime/calls` with the stored API key. The browser gets
only an SDP answer, not the API key or an ephemeral credential. Audio then travels
directly between browser and OpenAI. This is OpenAI's
[unified WebRTC interface](https://developers.openai.com/api/docs/guides/voice-webrtc).

The Realtime model handles conversation. Its single `delegate_to_agent` function
arrives through the WebRTC data channel and is forwarded to an authenticated,
CSRF-protected Agent Zero plugin endpoint. It logs the request in the selected
chat, calls `AgentContext.communicate(UserMessage(...))`, and awaits the normal
agent result, matching the core `/message` path. This avoids a second agent or a
separate conversation backend. Browser-forwarded tool calls are a supported
[server-control pattern](https://developers.openai.com/api/docs/guides/voice-server-controls).

After a tool call the client requests a brief acknowledgement with tools disabled
and an empty, separate response context, preventing it from solving the task in
the acknowledgement.
The conversation stays open while Agent Zero works. Results become function
outputs and are spoken when the voice model is free and you are not speaking.
Follow-up requests during the task become normal Agent Zero interventions.
VAD handles spoken interruptions; the Interrupt button cancels generation and
clears queued playback. Native media objects stay outside Alpine's reactive state.

## Exact browser test

1. Use headphones, open a new chat, and click **Realtime voice** (headset).
   Allow microphone access. The panel should change from Connecting to Listening.
2. Say “Hello, answer in one short sentence.” Verify you hear a reply and see captions.
3. Ask for a long explanation. While it speaks, say “Stop, just one sentence.”
   Check that playback stops and the next answer follows your interruption.
   Also try the **Interrupt** button.
4. Say “Use the terminal to calculate 17 times 23.” Expect a short acknowledgement,
   the task and agent progress in the chat, then a spoken result of **391**.
5. Ask for a harmless task that takes longer, such as “Run a command that waits
   ten seconds, then prints ready.” Keep talking during the wait. Add “Include
   the current UTC time too.” Verify the update and combined result in the chat.
6. Try **Mute**, **Unmute**, and **End call**. After ending, verify the browser's
   microphone indicator disappears. Start another call, then switch chats;
   the call should end rather than send work to the new chat.
7. Enable normal read-aloud before a call and verify you do not hear duplicate
   replies. End the call and verify normal microphone/read-aloud still work.
8. Change the voice/model in plugin configuration, save, and start a new call.
9. Disable the plugin, reload, and verify the headset button disappears while
   the original voice mode remains. Re-enable and reload to restore it.

## Automated verification

From this repository: `node --test tests/js/*.mjs`.

Inside an Agent Zero container with the plugin installed:

```sh
cd /a0
/opt/venv-a0/bin/python -m pytest usr/plugins/realtime_voice/tests -q
```

Pytest and pytest-asyncio are development dependencies, not plugin requirements.
Offline tests cover configuration, session payloads and mocked HTTP errors,
delegation/results/interventions/cancellation, and conversation event ordering.

For a billable live test without a microphone, use a harmless recording containing
a request such as “Use the terminal to calculate 17 times 23.” Convert it to mono
24 kHz PCM16 WAV if needed, then run:

```sh
cd /a0
/opt/venv-a0/bin/python -m usr.plugins.realtime_voice.scripts.wav_smoke /tmp/request.wav --output /tmp/reply.wav
```

This uses the same session builder and real delegation helper in a standalone
context; it prints transcripts and writes the response audio. It runs whatever
the recording requests, using the configured task agent. It does not attach to
an existing browser chat. The development-only `dev/browser-live.mjs` exercises
the actual UI/WebRTC path with synthetic microphone audio; see `dev/CHECKLIST.md`
for local verification evidence.

## Limitations and cleanup

- Keep the tab open. Ending/disconnecting the voice session does **not** cancel
  Agent Zero work already started; its result remains in chat. Use Agent Zero's
  normal stop control to stop that work. No automatic reconnect or result replay.
- Interruption stops speech, not a running agent task. Only one voice session per
  tab is intended; avoid simultaneous calls in multiple tabs for the same chat.
- Long delegation uses an HTTP request like `/message`. Reverse proxies must allow
  requests lasting as long as your tasks; a proxy timeout does not stop agent work.
- Recent chat messages are included at connection time, and long task results are
  trimmed for voice. Full agent answers stay in chat. Casual voice conversation
  captions are temporary, not persisted as Agent Zero chat messages.
- Audio/transcripts go to OpenAI. The plugin does not record audio on the server.
  Captions can be inaccurate; disabling the caption model disables user captions,
  not audio input or assistant transcripts. Headphones reduce echo/false interrupts.
- The browser can inspect/edit Realtime session events, as it already can submit
  tasks through Agent Zero's authenticated UI. This is not a public multi-tenant
  voice gateway. Never expose an unauthenticated Agent Zero instance publicly.
- Sessions are subject to OpenAI connection limits, account access, billing and
  network reachability. This plugin requires the Realtime API, not a ChatGPT plan.

End calls, uninstall through **Plugins → Realtime Voice → Delete**, and reload
open tabs. The plugin has no external services or owned dependencies to remove.
Normal chat history and the shared OpenAI API key remain. Scoped configuration
entries can be removed through Agent Zero's plugin configuration management.

The repository follows the [community plugin layout](https://github.com/agent0ai/a0-plugins):
runtime files, `plugin.yaml`, README, and LICENSE at root. Source is available at
[NoHara42/a0-realtime-voice](https://github.com/NoHara42/a0-realtime-voice).
The community-index submission is being prepared; the plugin is not yet listed.

See [SECURITY.md](SECURITY.md) for trust boundaries and data handling,
[CHANGELOG.md](CHANGELOG.md) for release changes, and [SUBMISSION.md](SUBMISSION.md)
for the exact publication and index-PR steps.
