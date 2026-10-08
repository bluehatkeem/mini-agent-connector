#!/usr/bin/env python3
"""Private-LAN Mini Agent Connector. Backend credentials stay on the host."""
import argparse
import concurrent.futures
import hmac
import ipaddress
import json
import os
from pathlib import Path
import secrets
import signal
import shutil
import subprocess
import threading
import time
import uuid
import wave
from configuration import Settings, DisabledTranscriber
from activity import classify_activity
from transcription import Transcriber
from metal_transcription import MetalTranscriber
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / '.runtime'
MAX_AUDIO = 16000 * 2 * 12
MAX_TEXT = 2000
TTL = 3600


def run_json(args, timeout=180):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        # Never return raw CLI stderr: it may contain private configuration.
        raise RuntimeError(f'{Path(args[0]).name} command failed ({result.returncode})')
    output = result.stdout
    for pos, char in enumerate(output):
        if char == '{':
            try:
                return json.loads(output[pos:])
            except json.JSONDecodeError:
                pass
    raise RuntimeError('Backend returned invalid JSON')


class Bridge:
    def __init__(self, runtime=RUNTIME, settings=None):
        self.settings = settings or Settings()
        self.runtime = runtime
        runtime.mkdir(mode=0o700, parents=True, exist_ok=True)
        runtime.chmod(0o700)
        token_file = runtime / 'device-token'
        if not token_file.exists():
            fd = os.open(token_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(secrets.token_urlsafe(32))
        token_file.chmod(0o600)
        self.token = token_file.read_text().strip()
        if len(self.token) < 32:
            raise ValueError('device-token must contain at least 32 characters')
        self.jobs = {}
        self.lock = threading.RLock()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.cli = self.settings.openclaw
        self.ffmpeg = self.settings.ffmpeg
        self.stt_engine = self.settings.stt_engine
        if self.stt_engine == 'metal':
            model = Path(self.settings.whisper_model).expanduser() if self.settings.whisper_model else runtime / 'ggml-small.bin'
            self.transcriber = MetalTranscriber(model, self.settings.whisper_server)
        elif self.stt_engine == 'pytorch':
            self.transcriber = Transcriber(self.settings.whisper_python)
        else:
            self.transcriber = DisabledTranscriber()

    def submit(self, text=None, pcm=None, speak=True):
        with self.lock:
            for key, job in list(self.jobs.items()):
                if time.time() - job['created'] > TTL and job['status'] in ('done', 'error'):
                    del self.jobs[key]
                    shutil.rmtree(self.runtime / key, ignore_errors=True)
            if sum(j['status'] not in ('done', 'error') for j in self.jobs.values()) >= 3:
                raise OverflowError('Device is busy; wait for current requests')
            key = uuid.uuid4().hex
            self.jobs[key] = dict(id=key, status='queued', created=time.time(), activity=classify_activity(text))
            self.executor.submit(self.process, key, text, pcm, speak)
            return dict(id=key, status='queued', activity=self.jobs[key]['activity'])

    def update(self, key, **fields):
        with self.lock:
            self.jobs[key].update(fields)

    def process(self, key, text, pcm, speak):
        process_started = time.monotonic()
        directory = self.runtime / key
        directory.mkdir(mode=0o700)
        try:
            if pcm is not None:
                self.update(key, status='transcribing')
                audio = directory / 'input.wav'
                with wave.open(str(audio), 'wb') as f:
                    f.setnchannels(1)
                    f.setsampwidth(2)
                    f.setframerate(16000)
                    f.writeframes(pcm)
                result = self.transcriber.transcribe(audio)
                self.update(key, transcription_ms=result['transcription_ms'], decode_ms=result['decode_ms'],
                            stt_engine=result.get('engine', 'whisper-pytorch'))
                text = result.get('text')
                if not isinstance(text, str) or not text.strip():
                    raise RuntimeError('No speech recognized; please try again')
                text = text.strip()[:MAX_TEXT]
                self.update(key, transcript=text, activity=classify_activity(text))
                audio.unlink(missing_ok=True)
            self.update(key, status='thinking')
            prompt = (
                'You are responding through a private small-screen desk companion. '
                'Keep your configured agent identity and follow your workspace startup instructions. '
                'This device has a separate conversation; do not assume it includes other chats. '
                'For prior work, personal context, preferences, or configured integrations, use your '
                'available memory tools and permitted bounded session history before answering. '
                'Report unavailable or partial recall honestly. Respect session visibility boundaries. '
                'Answer naturally in at most 60 words. Return plain text here, not via messaging tools. '
                'Use normal tool and approval policies for actions; verify success before claiming it. '
                '\n\nUser request: ' + text)
            message_file = directory / 'request.txt'
            message_file.write_text(prompt)
            agent_started = time.monotonic()
            command = [self.cli, 'agent', '--agent', self.settings.agent,
                       '--session-key', self.settings.session_key]
            if self.settings.model:
                command += ['--model', self.settings.model]
            if self.settings.thinking:
                command += ['--thinking', self.settings.thinking]
            command += ['--message-file', str(message_file), '--json', '--timeout', '150']
            result = run_json(command, timeout=165)
            body = result.get('result', result)
            meta = body.get('meta', {}).get('agentMeta', {})
            self.update(key, model=meta.get('model', 'unreported'),
                        agent_ms=round((time.monotonic()-agent_started)*1000))
            if result.get('status') not in (None, 'ok'):
                raise RuntimeError('Agent backend did not complete the request')
            reply = body.get('meta', {}).get('finalAssistantVisibleText') or '\n'.join(
                item.get('text', '') for item in body.get('payloads', []))
            if not reply or not reply.strip():
                raise RuntimeError('Agent returned no response; please try again')
            reply = reply.strip()[:2400]
            self.update(key, text=reply)
            if speak:
                speech_started = time.monotonic()
                self.update(key, status='speaking')
                try:
                    mp3 = directory / 'reply.mp3'
                    command = [self.cli, 'infer', 'tts', 'convert', '--text', reply[:900],
                               '--output', str(mp3), '--json']
                    if self.settings.tts_provider:
                        command += ['--provider', self.settings.tts_provider]
                    if self.settings.tts_voice:
                        command += ['--voice', self.settings.tts_voice]
                    result = run_json(command, timeout=90)
                    if not result.get('ok'):
                        raise RuntimeError('Speech synthesis unavailable')
                    raw = directory / 'reply.pcm'
                    subprocess.run([self.ffmpeg, '-nostdin', '-v', 'error', '-y', '-i', str(mp3),
                                    '-t', '45', '-ar', '16000', '-ac', '1', '-f', 's16le', str(raw)],
                                   check=True, capture_output=True, timeout=30)
                    with wave.open(str(directory / 'reply.wav'), 'wb') as f:
                        f.setnchannels(1)
                        f.setsampwidth(2)
                        f.setframerate(16000)
                        f.writeframes(raw.read_bytes())
                    self.update(key, audio_url=f'/v1/requests/{key}/audio.wav',
                                pcm_url=f'/v1/requests/{key}/audio.pcm', audio_format='pcm_s16le',
                                sample_rate=16000, channels=1)
                    mp3.unlink(missing_ok=True)
                except Exception:
                    self.update(key, audio_error='Voice unavailable; text response is ready')
            if speak:
                self.update(key, speech_ms=round((time.monotonic() - speech_started) * 1000))
            self.update(key, status='done')
        except subprocess.TimeoutExpired:
            self.update(key, status='error', error='Backend timed out; do not retry actions without checking their status')
        except Exception as exc:
            self.update(key, status='error', error=str(exc) if isinstance(exc, RuntimeError) else 'Backend request failed')
        finally:
            self.update(key, total_ms=round((time.monotonic() - process_started) * 1000))
            (directory / 'input.wav').unlink(missing_ok=True)
            (directory / 'input.json').unlink(missing_ok=True)
            (directory / 'request.txt').unlink(missing_ok=True)


class Handler(BaseHTTPRequestHandler):
    server_version = 'MiniAgentConnector/1'

    def log_message(self, fmt, *args):
        # Keep conversation text and credentials out of access logs.
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def respond(self, code, body, content_type='application/json'):
        data = json.dumps(body).encode() if content_type == 'application/json' else body
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        expected = 'Bearer ' + self.server.bridge.token
        if not hmac.compare_digest(self.headers.get('Authorization', '').encode('utf-8'), expected.encode('utf-8')):
            self.respond(401, {'error': 'Unauthorized'})
            return False
        return True

    def do_GET(self):
        if not self.authorized():
            return
        bridge = self.server.bridge
        if self.path == '/health':
            return self.respond(200, dict(ok=True, service='gero-device', protocol=1, max_audio_seconds=12,
                stt_engine=bridge.stt_engine,
                stt_ready=bridge.transcriber.process is not None and bridge.transcriber.process.poll() is None))
        parts = self.path.strip('/').split('/')
        if len(parts) in (3, 4) and parts[:2] == ['v1', 'requests']:
            key = parts[2]
            with bridge.lock:
                job = dict(bridge.jobs.get(key, {}))
            if not job:
                return self.respond(404, {'error': 'Request not found'})
            if len(parts) == 3:
                return self.respond(200, job)
            if parts[3] in ('audio.wav', 'audio.pcm') and job.get('status') == 'done':
                suffix = parts[3].split('.')[1]
                file = bridge.runtime / key / ('reply.' + suffix)
                if file.is_file():
                    return self.respond(200, file.read_bytes(), 'audio/wav' if suffix == 'wav' else 'application/octet-stream')
        self.respond(404, {'error': 'Not found'})

    def do_POST(self):
        if not self.authorized():
            return
        if self.path not in ('/v1/requests', '/v1/voice'):
            return self.respond(404, {'error': 'Not found'})
        try:
            if self.headers.get('Transfer-Encoding'):
                return self.respond(411, {'error': 'Content-Length required'})
            lengths = self.headers.get_all('Content-Length', [])
            if len(lengths) != 1:
                return self.respond(411, {'error': 'One Content-Length required'})
            length = int(lengths[0])
            maximum = MAX_AUDIO if self.path == '/v1/voice' else 10000
            if length < 1 or length > maximum:
                return self.respond(413, {'error': 'Invalid payload size'})
            data = self.rfile.read(length)
            if len(data) != length:
                return self.respond(400, {'error': 'Incomplete body'})
            if self.path == '/v1/voice':
                if length % 2 or length < 3200:
                    return self.respond(400, {'error': 'Send PCM16LE mono 16000Hz, 0.1 to 12 seconds'})
                if self.server.bridge.stt_engine == 'none':
                    return self.respond(503, {'error': 'Voice input is disabled; configure stt_engine'})
                voice_speak = self.headers.get('X-Gero-Speak', 'true').lower()
                if voice_speak not in ('true', 'false'):
                    return self.respond(400, {'error': 'X-Gero-Speak must be true or false'})
                job = self.server.bridge.submit(pcm=data, speak=voice_speak == 'true')
            else:
                body = json.loads(data)
                text = body.get('text') if isinstance(body, dict) else None
                if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
                    return self.respond(400, {'error': 'text must contain 1 to 2000 characters'})
                speak = body.get('speak', True)
                if not isinstance(speak, bool):
                    return self.respond(400, {'error': 'speak must be boolean'})
                job = self.server.bridge.submit(text=text.strip(), speak=speak)
            self.respond(202, job)
        except OverflowError as exc:
            self.respond(429, {'error': str(exc)})
        except (ValueError, UnicodeError):
            self.respond(400, {'error': 'Invalid JSON or Content-Length'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--config', type=Path, help='JSON configuration file')
    parser.add_argument('--runtime', type=Path, default=RUNTIME, help='Private runtime directory')
    parser.add_argument('--doctor', action='store_true', help='Check configuration and dependencies, then exit')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    try:
        settings = Settings.load(args.config)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    if args.doctor:
        raise SystemExit(settings.doctor(args.runtime))
    address = ipaddress.ip_address(args.host)
    if address.version != 4 or not address.is_private or address.is_unspecified or address.is_multicast or address.is_reserved:
        parser.error('Bind to a specific private LAN or loopback IP, not wildcard/public')
    os.umask(0o077)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.bridge = Bridge(args.runtime.expanduser().resolve(), settings)
    # Preload before accepting voice requests. Text remains usable if warmup fails.
    try:
        server.bridge.transcriber.warm()
    except Exception:
        print('Whisper warmup failed; next voice request will retry', flush=True)
    print(f'Mini Agent Connector listening at http://{args.host}:{args.port}', flush=True)
    def stop(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.bridge.executor.shutdown(wait=True)
        server.bridge.transcriber.close()
        server.server_close()


if __name__ == '__main__':
    main()
