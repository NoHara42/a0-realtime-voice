Initial public release of Realtime Voice for Agent Zero.

- Continuous OpenAI speech-to-speech over direct browser WebRTC.
- Interruptible replies, captions, mute, and session cleanup.
- Native Agent Zero task delegation with an immediate spoken acknowledgement and
  result narration; no third-party voice hosting.
- API key stays server-side; settings reuse Agent Zero's normal configuration.
- Theme-consistent settings and high-contrast headset control.

Validation: 42 Python tests and 11 JavaScript tests; live synthetic-audio WebRTC
delegation, terminal execution, spoken results and barge-in; install/uninstall,
dark/light styling, authentication and CSRF checks.

Install the attached `realtime_voice.zip` through Agent Zero's ZIP installer, or
use the Git installer with this repository URL. See README.md for setup and
SECURITY.md for data handling and the trusted-instance security model.

The community-index PR is pending owner approval; this release is directly
installable before an index listing is approved.
