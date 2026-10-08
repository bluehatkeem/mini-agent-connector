import json
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer
from server import Bridge, Handler
from configuration import Settings

class BridgeHTTPTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.bridge = Bridge(Path(self.temp.name), Settings(stt_engine='metal'))
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.bridge = self.bridge
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.bridge.executor.shutdown()
        self.temp.cleanup()
    def request(self, path, body=None, auth=True, extra_headers=None):
        headers = {'Authorization': 'Bearer ' + self.bridge.token} if auth else {}
        headers.update(extra_headers or {})
        req = urllib.request.Request(self.base + path, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as exc:
            with exc:
                return exc.code, json.load(exc)
    def test_auth_required_including_audio(self):
        for path in ['/health', '/v1/requests/foo', '/v1/requests/foo/audio.pcm']:
            self.assertEqual(self.request(path, auth=False)[0], 401)
    def test_health_and_input_validation(self):
        self.assertEqual(self.request('/health')[0], 200)
        for body in [b'{}', b'[]', b'{"text": ""}', b'{"text":123}', b'not-json']:
            self.assertEqual(self.request('/v1/requests', body)[0], 400)
        self.assertEqual(self.request('/v1/voice', b'123')[0], 400)
    def test_queue_limit(self):
        self.bridge.jobs = {str(i): {'status':'thinking', 'created':99999999999} for i in range(3)}
        self.assertEqual(self.request('/v1/requests', b'{"text":"hello"}')[0], 429)
    def test_audio_requires_completed_job(self):
        self.bridge.jobs['test'] = {'status':'thinking'}
        self.assertEqual(self.request('/v1/requests/test/audio.pcm')[0], 404)
    def test_voice_quiet_mode(self):
        with patch.object(self.bridge, 'submit', return_value={'id':'test','status':'queued','activity':'general'}) as submit:
            code, _ = self.request('/v1/voice', b'\0'*3200, extra_headers={'X-Gero-Speak':'false'})
            self.assertEqual(code, 202)
            self.assertIs(submit.call_args.kwargs['speak'], False)
        self.assertEqual(self.request('/v1/voice', b'\0'*3200, extra_headers={'X-Gero-Speak':'invalid'})[0],400)
    def test_text_activity_response_and_muted_request(self):
        with patch.object(self.bridge.executor, 'submit'):
            code, response = self.request('/v1/requests', b'{"text":"Check Gmail","speak":false}')
        self.assertEqual(code,202)
        self.assertEqual(response['activity'],'email')
        self.assertEqual(self.request('/v1/requests/'+response['id'])[1]['activity'],'email')
    def test_disabled_voice_is_rejected_before_queueing(self):
        self.bridge.stt_engine = 'none'
        self.assertEqual(self.request('/v1/voice', b'\0' * 3200)[0], 503)
        self.assertFalse(self.bridge.jobs)

    def test_wrong_and_non_ascii_bearer_are_rejected(self):
        for token in ('Bearer wrong', 'Bearer caf\xe9'):
            self.assertEqual(self.request('/health', extra_headers={'Authorization': token})[0], 401)

    def test_no_path_traversal(self):
        self.assertEqual(self.request('/v1/requests/../../device-token')[0], 404)

if __name__ == '__main__':
    unittest.main()
