import tempfile
import json
import uuid
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from server import Bridge
from configuration import Settings
from activity import classify_activity

class ActivityTest(unittest.TestCase):
    def test_common_requests(self):
        cases = {'Send an email about theCam': 'email', 'Check Gmail inbox': 'email',
                 'What is on my calendar?':'calendar', 'Remind me to sign my timesheet':'reminder',
                 'Turn on the hallway lights':'home', 'Design a 3D printed enclosure':'printing',
                 'Fix theCam login bug':'coding', 'theCam daily growth report':'thecam',
                 'Give me a market summary':'markets', 'Will it rain today?':'weather',
                 'Find farms nearby':'research', 'Tell me a joke':'general',
                 'I highlighted my notes':'general', 'The email says turn on lights':'email'}
        for text, expected in cases.items():
            with self.subTest(text=text): self.assertEqual(classify_activity(text), expected)
    def test_job_badge_survives_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp:
            b=Bridge(Path(temp))
            try:
                with patch.object(b.executor, 'submit'):
                    receipt=b.submit(text='Check Gmail')
                self.assertEqual(receipt['activity'],'email')
                self.assertEqual(b.jobs[receipt['id']]['activity'],'email')
                b.update(receipt['id'],status='thinking')
                self.assertEqual(b.jobs[receipt['id']]['activity'],'email')
            finally: b.executor.shutdown()
    def test_voice_badge_updates_after_transcription_without_speech(self):
        with tempfile.TemporaryDirectory() as temp:
            b=Bridge(Path(temp), Settings(model='example/model', thinking='low', stt_engine='metal'));key=uuid.uuid4().hex
            b.jobs[key]={'id':key,'status':'queued','created':time.time(),'activity':'general'}
            def transcribe(args, **kwargs):
                (Path(temp)/key/'input.json').write_text(json.dumps({'text':'Read my Gmail inbox'}))
            try:
                with patch.object(b.transcriber, 'transcribe', return_value={'text':'Read my Gmail inbox', 'transcription_ms':12, 'decode_ms':10}), patch('server.run_json',return_value={'result':{'payloads':[{'text':'Test response'}]}}) as backend:
                    b.process(key,None,b'\0'*3200,False)
                job=b.jobs[key]
                self.assertEqual(job['activity'],'email')
                self.assertEqual(job['status'],'done')
                self.assertEqual(job['transcript'],'Read my Gmail inbox')
                self.assertNotIn('pcm_url',job)
                self.assertFalse((Path(temp)/key/'input.wav').exists())
                self.assertGreaterEqual(job['total_ms'], 0)
                self.assertEqual(backend.call_count,1)
                args=backend.call_args.args[0]
                self.assertEqual(args[args.index('--model')+1],'example/model')
                self.assertEqual(args[args.index('--thinking')+1],'low')
                self.assertEqual(args[args.index('--session-key')+1],'mini-agent')
            finally:b.executor.shutdown()
if __name__=='__main__':unittest.main()
