# Security model

Realtime Voice is an extension of a trusted Agent Zero installation, not a public
voice gateway or an independent sandbox. Anyone allowed to use that installation
can ask its normal agent to run tasks, including commands and file operations.
Enable Agent Zero login and use HTTPS for remote access. The plugin inherits
Agent Zero's authentication and context-access model; it does not add per-user
tenant isolation or approval rules.

## Data and credentials

- The OpenAI API key is read server-side through Agent Zero's provider-key helper.
  It is not placed in plugin configuration, returned to the browser, or packaged.
  Key storage and at-rest protection are managed by Agent Zero.
- The session endpoint calls the fixed HTTPS OpenAI Realtime URL. Client input
  cannot select an upstream host. Audio goes directly from the browser to OpenAI.
- Recent chat excerpts, spoken instructions, and delegated results are sent to
  OpenAI. Set history messages to zero to omit the initial chat excerpt.
- The plugin records no audio. Delegated requests/results remain in normal Agent
  Zero chat history; temporary captions remain in the browser until the next call
  or reload. Test scripts explicitly create synthetic WAV artifacts.
- Provider exception text is not echoed by the session endpoint or forwarded as
  a delegation failure. Check the normal Agent Zero chat for task error details.
- Caption content is rendered as text with Alpine `x-text`, never as HTML.

## Requests and delegation

All three endpoints require the framework's normal authentication and CSRF
protection. Session SDP is limited to 128 KiB of characters; task text is limited
to 20,000 characters. These limits bound accepted payloads after JSON parsing;
deployment-level request/body limits and rate limiting belong in the server or
reverse proxy. Authentication does not prevent an authorized user from incurring
OpenAI usage charges.

The browser receives function calls and submits them to the backend. Tool-call
IDs are correlation data, not proof of authorization. A trusted authenticated
browser can submit tasks directly, just as it can through Agent Zero's normal
message API. Models and transcriptions can make mistakes or follow misleading
instructions: review important actions and restrict the agent's underlying tools
and environment according to your needs. Prompts are not a security boundary.

Ending a call stops local audio and WebRTC; it does not stop tasks already
dispatched to Agent Zero. Use the normal agent stop control for those tasks.
Disable/uninstall rejects new session/delegation requests but cannot remotely
close an already connected browser-to-OpenAI media session. End calls and reload
open tabs when disabling or uninstalling.

## Reporting

For a published repository, use GitHub's private **Report a vulnerability** entry
under the Security tab. The repository owner should enable private vulnerability
reporting before publication. Do not post API keys, recordings, chat contents, or
credentials in public issues. If private reporting is unavailable, ask for a
private contact channel without including exploit details or sensitive material.

The local release review in `dev/SECURITY_REVIEW.md` describes what was checked
and what remains untested; it is not an independent penetration-test certification.
