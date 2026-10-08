"""One loaded small English-configured Whisper model, serial requests over stdio."""
import json
import sys
import time
import whisper

model = whisper.load_model('small')
print(json.dumps({'ready': True}), flush=True)
for line in sys.stdin:
    try:
        request = json.loads(line)
        started = time.monotonic()
        result = model.transcribe(request['path'], language='en', fp16=False, verbose=None,
                                  beam_size=5, best_of=5)
        print(json.dumps({'text': result['text'],
                          'decode_ms': round((time.monotonic() - started) * 1000)}), flush=True)
    except Exception:
        print(json.dumps({'error': 'transcription failed'}), flush=True)
