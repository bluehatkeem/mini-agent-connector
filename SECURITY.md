# Security and privacy

This is a trusted-LAN, single-owner connector. It is not an Internet-facing API,
a sandbox for the agent, or a substitute for OpenClaw's own access controls.

- Bind only to loopback or a specific trusted private IPv4 address. Do not use
  router port forwarding, a public tunnel, or wildcard binding.
- HTTP is unencrypted: anyone able to observe LAN traffic can capture the bearer
  and content. The bearer permits agent requests (including actions allowed by
  your agent) and reads of all jobs on that instance. Use an isolated trusted
  network. No TLS termination or multi-user authorization is implemented here.
- Backend credentials stay in OpenClaw. Provision only the separate random
  device token. It is generated locally, never shipped in this repo.
- Use a dedicated agent with appropriate tool policies when a device is shared.
  Memory visibility and approval rules are enforced by OpenClaw, not by a new
  authorization layer in the connector. The prompt does not provide a security
  boundary against malicious input or prompt injection.
- STT runs locally after model download. Transcribed text goes to your agent and
  potentially its cloud model provider. Answer text goes to the configured TTS
  provider when speech is requested. This is not necessarily a fully offline system.
- No microphone is opened by the connector. The device/client supplies an explicit
  recording. Access logs omit credentials and conversation text. CLI stderr is
  not returned to clients.

## Retention and rotation

Runtime directory permissions are 0700; bearer permissions are 0600. `.runtime/`,
local configuration, audio, model weights, and logs are ignored by Git.

Raw input WAV and the temporary prompt file are deleted in each job's `finally`
block. Completed job metadata stays in memory; generated audio stays in its
runtime subdirectory. Completed/errored jobs older than one hour are removed
**on the next submission**, not by a background timer. If no new request arrives,
files can remain longer. A crash can leave temporary recordings, prompts, or
outputs. Old runtime directories are not automatically recovered or pruned after
restart. For sensitive use, stop the connector and remove old UUID-named job
directories manually; keep the token/model files if still needed. Do not mistake
this lazy cleanup for a guaranteed one-hour deletion policy.

OpenClaw retains conversations according to **its own** session/history policies.
Deleting local audio does not erase provider logs or OpenClaw session history.

To rotate: stop this connector, remove **its** `device-token` file, restart it,
and provision the newly generated token into your client/device. Old clients
stop authenticating. Restart is required; the running server caches the token.
Never rotate or reuse another installation's runtime directory accidentally.

## Before publication

Inspect `git diff --cached`, `git ls-files`, and run `python3 scripts/audit_release.py`.
The scanner checks staged content and filenames with heuristics; it cannot prove
that arbitrary secrets or private prose are absent. Review all new files. Never
include flash/NVS backups, logs, real tokens, personal memories, or production
configuration. Do not import the live installation's Git history.

For a vulnerability report after publication, use GitHub's private vulnerability
reporting if the maintainer has enabled it. Never post credentials in an issue.
