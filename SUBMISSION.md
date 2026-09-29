# Submit Realtime Voice to the Agent Zero plugin index

Current release: **0.1.2**, plugin name **realtime_voice**.
Source repository: [NoHara42/a0-realtime-voice](https://github.com/NoHara42/a0-realtime-voice).
Index fork: [NoHara42/a0-plugins](https://github.com/NoHara42/a0-plugins), branch
`add-realtime-voice`. The index PR must remain unsubmitted until the owner has
reviewed and approved the proposed title, body, and diff.

## 1. Publish the plugin repository

The public source repository is `NoHara42/a0-realtime-voice`.
Publish this repository's contents at its root, including
`plugin.yaml`, README, LICENSE, SECURITY, implementation, and tests. Do not nest
the implementation inside another `realtime_voice/` directory in Git.

Initial publication commands are recorded below for reference; do not rerun
repository setup or an initial-release commit after publication:

```sh
node --test tests/js/*.mjs
python3 scripts/package.py
python3 scripts/check_release.py
git add .gitignore LICENSE README.md SECURITY.md CHANGELOG.md SUBMISSION.md plugin.yaml default_config.yaml package.json api helpers prompts extensions webui scripts tests dev
git diff --cached --check
git diff --cached --stat
# Review the staged contents, then:
git commit -m "Release Realtime Voice 0.1.1"
git branch -M main
git remote add origin https://github.com/NoHara42/a0-realtime-voice.git
git push -u origin main
```

The local repository's `origin` points to that public repository.
`.gitignore` excludes runtime configuration, credentials, synthetic
recordings, screenshots from local checks, and built ZIPs. Inspect the staged
diff yourself before pushing. For subsequent releases, create the matching version tag (currently `v0.1.2`) and attach
`dist/realtime_voice.zip`; the Git installer uses the repository itself.

GitHub private vulnerability reporting is enabled. Verify that
the default branch publicly serves root `plugin.yaml` with `name: realtime_voice`.

## 2. Add the index entry

Fork [agent0ai/a0-plugins](https://github.com/agent0ai/a0-plugins) and create a branch.
Before adding an entry, check the current index for an existing `realtime_voice`
name or your canonical repository URL; use a unique name or update an existing
entry as appropriate.

Create exactly `plugins/realtime_voice/index.yaml` in the fork. Copy
`dev/index.yaml.example`, which contains the public source URL.
The example already uses recommended `audio`, `agents`,
and `integration` tags. Do **not** copy runtime code or `plugin.yaml` into the index.

An image is optional. If you add one, use a square `thumbnail.png`, `.jpg`, `.jpeg`,
or `.webp`, no larger than 20 KiB. Optional screenshots are up to five public image
URLs in `index.yaml`, each at most 2 MiB. Omit them until they are publicly hosted.

## 3. Open the PR

Commit the entry, validate it, and show the proposed PR to the owner. Only after
approval, open a PR against `agent0ai/a0-plugins:main` with title:

> Add Realtime Voice plugin

Suggested description:

> Adds interruptible OpenAI Realtime speech-to-speech to Agent Zero. The browser
> connects directly to OpenAI over WebRTC; the API key remains server-side.
> Tasks use the normal Agent Zero agent and chat, with spoken acknowledgements
> and results. Installation, settings, disable/uninstall, and real audio delegation
> were tested locally. See the plugin README and SECURITY.md for setup and trust
> boundaries.

The upstream CI validates the committed PR, reachable public repository, root
manifest/name, duplicates, metadata limits, and any image URLs. Address its checks
and then await maintainer review. A local metadata check cannot replace this
because there is no published repository to validate yet.

Current reference rules: [index README](https://github.com/agent0ai/a0-plugins),
[recommended tags](https://github.com/agent0ai/a0-plugins/blob/main/TAGS.md), and
[validator](https://github.com/agent0ai/a0-plugins/blob/main/scripts/validate_plugin_submission.py).
Recheck those when submitting; they can change.
