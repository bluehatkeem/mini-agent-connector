import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from metal_transcription import MetalTranscriber

class MetalWorkerTest(unittest.TestCase):
    def test_reuse_and_explicit_decoding(self):
        w=MetalTranscriber('/unused');proc=Mock();proc.poll.return_value=None
        w.process=proc;w.url='http://127.0.0.1:12345'
        with tempfile.TemporaryDirectory() as d:
            audio=Path(d)/'test.wav';audio.write_bytes(b'RIFFtest')
            with patch.object(w.http,'open',side_effect=lambda *a,**k:io.BytesIO(b'{"text":"hello"}')) as request:
                self.assertEqual(w.transcribe(audio)['text'],'hello')
                self.assertEqual(w.transcribe(audio)['engine'],'whisper.cpp-metal')
                self.assertEqual(request.call_count,2)
                body=request.call_args.args[0].data
                self.assertIn(b'name="beam_size"\r\n\r\n5',body)
                self.assertIn(b'name="best_of"\r\n\r\n5',body)
        self.assertIs(w.process,proc);w.close()

    def test_timeout_reaps_worker(self):
        w=MetalTranscriber('/unused');proc=Mock();proc.poll.return_value=None
        w.process=proc;w.url='http://127.0.0.1:12345'
        with tempfile.TemporaryDirectory() as d:
            audio=Path(d)/'test.wav';audio.write_bytes(b'RIFFtest')
            with patch.object(w.http,'open',side_effect=TimeoutError):
                with self.assertRaisesRegex(RuntimeError,'Local Metal'):w.transcribe(audio)
        self.assertIsNone(w.process);proc.kill.assert_called_once();proc.wait.assert_called_once()
