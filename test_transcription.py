import unittest
from unittest.mock import Mock, patch
from transcription import Transcriber

class WorkerTest(unittest.TestCase):
    def test_live_worker_is_reused(self):
        worker = Transcriber('/not/needed')
        proc = Mock(); proc.poll.return_value = None
        worker.process = proc
        with patch.object(worker, 'read', return_value={'text':'hello','decode_ms':2}):
            first = worker.transcribe('/tmp/a.wav')
            second = worker.transcribe('/tmp/b.wav')
        self.assertIs(worker.process, proc)
        self.assertEqual(proc.stdin.write.call_count, 2)
        self.assertEqual(first['text'], second['text'])
        self.assertIn('transcription_ms', second)
        worker.close()

    def test_timeout_discards_worker_and_next_request_can_restart(self):
        worker = Transcriber('/not/needed')
        proc = Mock(); proc.poll.return_value = None
        worker.process = proc
        with patch.object(worker, 'read', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError): worker.transcribe('/tmp/a.wav')
        self.assertIsNone(worker.process)
        proc.kill.assert_called_once()
        replacement = Mock(); replacement.poll.return_value = None
        def restart(): worker.process = replacement
        with patch.object(worker, 'start', side_effect=restart), patch.object(worker, 'read', return_value={'text':'recovered'}):
            self.assertEqual(worker.transcribe('/tmp/b.wav')['text'], 'recovered')
        worker.close()
