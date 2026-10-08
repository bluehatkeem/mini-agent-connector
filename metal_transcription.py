"""Persistent whisper.cpp/Metal worker on an ephemeral loopback-only port."""
import atexit
import json
from pathlib import Path
import socket
import subprocess
import threading
import time
import urllib.request
import uuid


class MetalTranscriber:
    def __init__(self, model, executable='whisper-server'):
        self.model = Path(model)
        self.executable = executable
        self.process = None
        self.url = None
        self.lock = threading.Lock()
        # Bypass any system HTTP proxy: recorded audio never leaves this Mac.
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        atexit.register(self.close)

    def close(self):
        proc, self.process = self.process, None
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            proc.wait()

    def start(self):
        if self.process is not None and self.process.poll() is None:
            return
        self.close()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.url = 'http://127.0.0.1:' + str(port)
        self.process = subprocess.Popen(
            [self.executable, '--host', '127.0.0.1', '--port', str(port),
             '--model', str(self.model), '--language', 'en', '--beam-size', '5',
             '--best-of', '5', '--public', str(self.model.parent / 'no-public-files')],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError('Metal transcription worker stopped')
            try:
                with self.http.open(self.url + '/health', timeout=1) as response:
                    if response.status == 200:
                        return
            except OSError:
                pass
            time.sleep(0.1)
        raise TimeoutError('Metal transcription startup timed out')

    def warm(self):
        with self.lock:
            try:
                self.start()
            except Exception:
                self.close()
                raise

    def transcribe(self, audio):
        with self.lock:
            started = time.monotonic()
            try:
                self.start()
                boundary = uuid.uuid4().hex
                parts = []
                for name, value in [('response_format', 'json'), ('language', 'en'),
                                    ('beam_size', '5'), ('best_of', '5')]:
                    parts.append(('--' + boundary + '\r\nContent-Disposition: form-data; name="' + name + '"\r\n\r\n' + value + '\r\n').encode())
                parts.append(('--' + boundary + '\r\nContent-Disposition: form-data; name="file"; filename="input.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode())
                parts.extend([Path(audio).read_bytes(), ('\r\n--' + boundary + '--\r\n').encode()])
                request = urllib.request.Request(self.url + '/inference', data=b''.join(parts),
                    headers={'Content-Type': 'multipart/form-data; boundary=' + boundary})
                decode_started = time.monotonic()
                with self.http.open(request, timeout=120) as response:
                    result = json.load(response)
                if not isinstance(result.get('text'), str):
                    raise RuntimeError('Metal transcription returned invalid text')
                return {'text': result['text'], 'engine': 'whisper.cpp-metal',
                        'decode_ms': round((time.monotonic() - decode_started) * 1000),
                        'transcription_ms': round((time.monotonic() - started) * 1000)}
            except Exception:
                self.close()
                raise RuntimeError('Local Metal transcription failed') from None
