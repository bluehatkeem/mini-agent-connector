import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from configuration import Settings
from server import Bridge


class ConfigurationTest(unittest.TestCase):
    def test_strict_config_and_portable_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'config.json'
            for value in ([], {'unknown': 'x'}, {'stt_engine': 'cloud'}, {'model': 2}, {'session_key': ''}):
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    Settings.load(path)
            path.write_text('{"agent":"desk","model":"provider/model"}')
            cfg = Settings.load(path)
            self.assertEqual(cfg.agent, 'desk')
            self.assertEqual(cfg.stt_engine, 'none')

    def test_inherit_agent_model_and_session_no_delivery(self):
        with tempfile.TemporaryDirectory() as d:
            bridge = Bridge(Path(d), Settings(agent='desk', session_key='my-companion'))
            try:
                with patch.object(bridge.executor, 'submit'):
                    job = bridge.submit(text='hello', speak=False)
                with patch('server.run_json', return_value={'payloads': [{'text': 'Hello'}]}) as backend:
                    bridge.process(job['id'], 'hello', None, False)
                command = backend.call_args.args[0]
                self.assertEqual(command[command.index('--agent') + 1], 'desk')
                self.assertEqual(command[command.index('--session-key') + 1], 'my-companion')
                self.assertNotIn('--model', command)
                self.assertNotIn('--thinking', command)
                self.assertNotIn('--deliver', command)
                self.assertEqual(bridge.jobs[job['id']]['status'], 'done')
                self.assertFalse((Path(d) / job['id'] / 'request.txt').exists())
                self.assertEqual((Path(d) / 'device-token').stat().st_mode & 0o777, 0o600)
                self.assertEqual(Path(d).stat().st_mode & 0o777, 0o700)
            finally:
                bridge.executor.shutdown()

    def test_voice_failure_removes_recording(self):
        with tempfile.TemporaryDirectory() as d:
            bridge = Bridge(Path(d))
            try:
                with patch.object(bridge.executor, 'submit'):
                    job = bridge.submit(pcm=b'\0' * 3200, speak=False)
                bridge.process(job['id'], None, b'\0' * 3200, False)
                self.assertEqual(bridge.jobs[job['id']]['status'], 'error')
                self.assertFalse((Path(d) / job['id'] / 'input.wav').exists())
            finally:
                bridge.executor.shutdown()

    def test_tts_failure_preserves_text(self):
        with tempfile.TemporaryDirectory() as d:
            bridge = Bridge(Path(d))
            try:
                with patch.object(bridge.executor, 'submit'):
                    job = bridge.submit(text='hello')
                with patch('server.run_json', side_effect=[{'payloads':[{'text':'Hello'}]}, RuntimeError('private backend detail')]):
                    bridge.process(job['id'], 'hello', None, True)
                self.assertEqual(bridge.jobs[job['id']]['status'], 'done')
                self.assertEqual(bridge.jobs[job['id']]['text'], 'Hello')
                self.assertNotIn('private', bridge.jobs[job['id']]['audio_error'])
            finally:
                bridge.executor.shutdown()
