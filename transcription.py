"""Persistent, bounded local Whisper subprocess; no credentials or network."""
import atexit
import json
from pathlib import Path
import select
import subprocess
import threading
import time


class Transcriber:
    def __init__(self, executable):
        self.executable = executable
        self.process = None
        self.lock = threading.Lock()
        atexit.register(self.close)

    def close(self):
        proc, self.process = self.process, None
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            proc.stdin.close()
            proc.stdout.close()

    def read(self, timeout):
        if not select.select([self.process.stdout], [], [], timeout)[0]:
            raise TimeoutError('Local transcription timed out')
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError('Local transcription worker stopped')
        result = json.loads(line)
        if result.get('error'):
            raise RuntimeError('Local transcription failed')
        return result

    def start(self):
        if self.process is not None and self.process.poll() is None:
            return
        self.close()
        # Explicit interpreter avoids fragile pip launcher/shebang assumptions.
        interpreter = self.executable
        self.process = subprocess.Popen(
            [interpreter, '-u', str(Path(__file__).with_name('whisper_worker.py'))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1)
        self.read(120)

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
                self.process.stdin.write(json.dumps({'path': str(audio)}) + '\n')
                self.process.stdin.flush()
                result = self.read(120)
                result['transcription_ms'] = round((time.monotonic() - started) * 1000)
                return result
            except Exception:
                # Never leave a wedged worker for the next request. Do not retry actions.
                self.close()
                raise
