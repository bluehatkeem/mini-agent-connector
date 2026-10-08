# Device protocol v1

All routes require `Authorization: Bearer <device-token>`, including health and
both audio routes. Fixed `Content-Length` is required for POST bodies; chunked
transfer is not supported. Responses have `Content-Length`, `Cache-Control:
no-store`, and close the connection. Poll approximately once per second.

| Route | Request | Response |
| --- | --- | --- |
| `GET /health` | none | `200`, bridge status, `protocol:1`, `max_audio_seconds:12`, STT engine/readiness |
| `POST /v1/requests` | JSON `{"text":"Hello","speak":false}` | `202`, job ID, `queued` status, activity |
| `POST /v1/voice` | binary PCM16LE, mono, 16000 Hz | Same `202` receipt |
| `GET /v1/requests/{id}` | none | Job status, answer and optional audio metadata |
| `GET /v1/requests/{id}/audio.pcm` | none | Header-free signed PCM16LE mono 16000 Hz |
| `GET /v1/requests/{id}/audio.wav` | none | Same audio in a WAV container |

`/health` retains the legacy `service:"gero-device"` identifier for existing
clients. It proves reachability, **not** successful agent/provider access.
`stt_ready` indicates a running worker, not audio quality or GPU verification.

Text: 1–2000 characters, with `speak` boolean defaulting to true. Voice:
3200–384000 bytes, even-sized (0.1–12 seconds). Voice header
`X-Gero-Speak: false` skips synthesis; omitted defaults true. This header name is
preserved for existing Mini Gero clients. Voice requests return 503 when STT is disabled.

Pipeline: `queued` → [`transcribing`] → `thinking` → [`speaking`] → `done` or
`error`. `speaking` means **host synthesis**, not that the device has played any
audio. `text` may appear before `done`. Fetch audio only on `done`; speech failure
returns `done` with the successful text and `audio_error`, without audio URLs.

Example completed job (fields omitted when not applicable):

```json
{
  "id": "0123456789abcdef0123456789abcdef",
  "status": "done",
  "created": 0,
  "activity": "general",
  "text": "Hello!",
  "transcript": "Hello",
  "model": "reported-model-id",
  "stt_engine": "whisper.cpp-metal",
  "transcription_ms": 320,
  "decode_ms": 280,
  "agent_ms": 2500,
  "speech_ms": 900,
  "total_ms": 3720,
  "audio_url": "/v1/requests/0123456789abcdef0123456789abcdef/audio.wav",
  "pcm_url": "/v1/requests/0123456789abcdef0123456789abcdef/audio.pcm",
  "audio_format": "pcm_s16le",
  "sample_rate": 16000,
  "channels": 1
}
```

Timing fields are observed host times. `total_ms` excludes queueing, network
upload/polling, and device playback. `model` is the backend-reported value or
`unreported`, not an independent proof of provider execution.

One worker processes jobs serially; at most three are outstanding. The token
and conversation are per **connector instance**, not per client: all clients
holding the same token can read that instance's jobs. Use separate runtime
directories, ports, tokens, and session keys for separate people/devices.

Activity categories: `general`, `email`, `calendar`, `reminder`, `home`,
`printing`, `coding`, `thecam`, `markets`, `weather`, `research`. `thecam` is a
legacy app/business badge ID retained for firmware compatibility. Classification
is keyword-based intent metadata, **never proof of tool execution or success**.

Errors: 400 malformed input; 401 missing/bad bearer; 404 unknown resource or audio
not ready; 411 missing/ambiguous fixed length or chunked transfer; 413 invalid
payload size; 429 queue full; 503 voice disabled. An accepted job can later reach
`error` with an error string. No automatic retry or idempotency key exists.

Agent CLI timeout is 150s (165s process timeout); local STT has 120s startup and
120s inference bounds; TTS is 90s plus 30s conversion. Account for queueing. An
action may already have happened when a request times out or the host restarts:
**check its status before resubmitting**. Restart loses in-memory jobs/results.

Replies are prompted to be at most 60 words, displayed text capped at 2400
characters, speech input text capped at 900 characters, and generated speech at
45 seconds. These limits are independent of your firmware's buffer limits.
