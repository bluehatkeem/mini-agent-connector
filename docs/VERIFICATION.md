# Local extraction verification

Verified October 8, 2026 on an Apple Silicon Mac. This records the extracted
connector's checks, not a claim that every platform or physical board was tested.

- Fresh virtual environment setup and dependency doctor succeeded.
- **20 automated tests passed**: authentication, malformed input, queue limits,
  quiet mode, audio readiness, traversal rejection, default-disabled voice,
  portable configuration, backend argument routing, token permissions, failure
  cleanup, graceful TTS failure, worker reuse and timeout recovery.
- Isolated real connector instance: separate loopback port, runtime/token, and
  OpenClaw conversation. Text input returned the correct arithmetic answer and
  111,456 bytes of 16-kHz mono PCM speech. TTS used the configured provider.
- A saved synthetic recording (no room microphone capture) passed through local
  whisper.cpp and the real agent, returning the correct answer. Observed STT was
  313 ms; total processing 6,879 ms. These are single observations, not benchmarks
  or guarantees. Proper-name transcription was imperfect; no accuracy parity claim.
- Staged-file privacy scan passed, including direct checks that neither the
  existing installation's bearer nor the isolated test bearer was present.
- A clean source-only checkout passed setup and all tests; no models, credentials,
  local configurations, recordings, production logs, or private Git history are
  included in the source tree.

Not verified here: fresh upstream model download, PyTorch inference on another
machine, Linux hardware, GitHub Actions execution before push, or physical
microphone/speaker/display behavior with this extracted repository. The original
Mini Gero service and firmware were not changed or restarted.
