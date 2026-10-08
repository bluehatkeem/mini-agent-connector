"""Explicit, non-secret connector settings. No credentials belong in this file."""
from dataclasses import dataclass, fields
import json
from pathlib import Path
import shutil
import sys


class DisabledTranscriber:
    process = None

    def warm(self):
        pass

    def close(self):
        pass

    def transcribe(self, audio):
        raise RuntimeError('Voice input is disabled; configure stt_engine')


@dataclass(frozen=True)
class Settings:
    agent: str = 'main'
    session_key: str = 'mini-agent'
    model: str = ''
    thinking: str = ''
    stt_engine: str = 'none'
    whisper_model: str = ''
    whisper_server: str = 'whisper-server'
    whisper_python: str = sys.executable
    tts_provider: str = ''
    tts_voice: str = ''
    openclaw: str = 'openclaw'
    ffmpeg: str = 'ffmpeg'

    def __post_init__(self):
        for field in fields(self):
            value = getattr(self, field.name)
            if not isinstance(value, str) or any(c in value for c in '\x00\r\n'):
                raise ValueError(f'{field.name} must be a single-line string')
        for name in ('agent', 'session_key', 'openclaw', 'ffmpeg', 'whisper_server', 'whisper_python'):
            if not getattr(self, name).strip():
                raise ValueError(f'{name} cannot be empty')
        if self.stt_engine not in ('none', 'metal', 'pytorch'):
            raise ValueError('stt_engine must be none, metal, or pytorch')
        if self.thinking not in ('', 'off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'adaptive', 'max', 'ultra'):
            raise ValueError('Unsupported thinking level')

    @classmethod
    def load(cls, path=None):
        if path is None:
            return cls()
        try:
            data = json.loads(Path(path).read_text())
        except json.JSONDecodeError:
            raise ValueError('Configuration must be valid JSON') from None
        if not isinstance(data, dict):
            raise ValueError('Configuration must be a JSON object')
        unknown = set(data) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError('Unknown configuration keys: ' + ', '.join(sorted(unknown)))
        return cls(**data)

    def doctor(self, runtime):
        import subprocess
        failures = 0
        print('Checking local dependencies only; no agent requests will be sent.')
        commands = [('OpenClaw (required)', self.openclaw)]
        if self.stt_engine == 'metal':
            commands.append(('whisper.cpp server', self.whisper_server))
        if self.stt_engine == 'pytorch':
            commands.append(('Whisper Python', self.whisper_python))
        for label, executable in commands:
            available = shutil.which(executable) is not None
            print(f'{label}: {"OK" if available else "MISSING"}')
            failures += not available
        print('ffmpeg (needed for speech output): ' + ('OK' if shutil.which(self.ffmpeg) else 'MISSING'))
        if self.stt_engine == 'metal':
            model = Path(self.whisper_model).expanduser() if self.whisper_model else Path(runtime).expanduser() / 'ggml-small.bin'
            available = model.is_file() and model.stat().st_size > 0
            print('Whisper GGML model: ' + ('OK' if available else 'MISSING'))
            failures += not available
        elif self.stt_engine == 'pytorch' and shutil.which(self.whisper_python):
            try:
                result = subprocess.run([self.whisper_python, '-c', 'import whisper'],
                                        capture_output=True, timeout=30)
                available = result.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                available = False
            print('Python whisper import: ' + ('OK' if available else 'MISSING'))
            failures += not available
        print('STT: ' + self.stt_engine)
        print('Provider authentication, CLI compatibility, and model availability need a live smoke test.')
        return 1 if failures else 0
