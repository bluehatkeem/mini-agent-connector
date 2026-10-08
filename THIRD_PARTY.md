# Dependencies and provenance

This repository contains the original Mini Gero **host connector** extracted
into a portable project. The connector source and included
documentation screenshots are provided under the repository's MIT license.
The four `docs/images/mini-gero-*.png` files are unmodified avatar framebuffer
captures from Mini Gero v0.13, captured during on-device expression verification.
The character artwork was created with AI image generation for Mini Gero. These
are example captures, not the complete sprite/animation pack or physical-device photos.
No vendor firmware, hardware drivers, flash dumps, model weights, or third-party
source code is bundled.

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
