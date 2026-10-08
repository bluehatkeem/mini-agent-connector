# Contributing

Python 3.10+; connector runtime uses only the standard library. Optional STT
packages belong in a virtual environment. Keep user configuration out of source.

```sh
python3 -m unittest discover -v
git add <reviewed-files>
python3 scripts/audit_release.py
git diff --cached --check
git diff --cached
```

Tests use temporary runtime directories and mock the agent/STT subprocesses;
they need no credentials, GPU, device, model download, or network service. Local
HTTP tests bind an ephemeral loopback port. CI runs on macOS and Linux.

Preserve protocol-v1 compatibility: especially PCM format, receipt/poll states,
quiet mode, and existing legacy identifiers. Add meaningful regression coverage
for transport, credential handling, lifecycle, or configuration changes. Do not
claim mocked tests validate a physical device or upstream provider availability.

For a real smoke test, start a separate connector instance with a separate
runtime, port and OpenClaw session key. Use the example client's harmless default
question. Do not change a user's production agent, firmware, or conversation
settings just to run tests. Agent actions must not be automatically replayed.
