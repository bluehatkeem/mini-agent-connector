# Dependencies and provenance

This repository contains the original Mini Gero **host connector** extracted
into a portable project. Its MIT license applies to the connector source only.
No vendor firmware, hardware drivers, artwork, flash dumps, model weights, or
third-party source code is bundled.

Separately installed dependencies retain their own licenses and terms:

| Component | Purpose / upstream |
| --- | --- |
| Python | Runtime; [python.org](https://www.python.org/) |
| OpenClaw | Agent gateway/CLI and provider configuration; [docs](https://docs.openclaw.ai/) |
| whisper.cpp | Optional local STT worker; [source](https://github.com/ggml-org/whisper.cpp), MIT |
| OpenAI Whisper | Optional Python STT and original model; [source and model license](https://github.com/openai/whisper), MIT |
| GGML Whisper model | Optional converted weights; [repository](https://huggingface.co/ggerganov/whisper.cpp) |
| FFmpeg | Optional speech conversion; [licensing](https://ffmpeg.org/legal.html), LGPL/GPL depending on build |
| Model/TTS providers | Optional configured services; each provider's terms, credentials, and costs apply |

No dependency versions are silently pinned or claimed reproducible. The inherited
Metal integration was verified with whisper.cpp 1.9.5. The download example uses
the upstream model's `main` revision and is not checksum-pinned. For reproducible
rollouts, select an upstream revision and record/verify the model's trusted
checksum before installing it. Models are intentionally excluded from Git.
