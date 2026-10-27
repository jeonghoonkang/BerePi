import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from creator import analyze, generate
from runtime_template import _python_jev_creator_decide as decide


class CreatorTests(unittest.TestCase):
    def test_class_scope_and_overlapping_conditions(self):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / 'main.py'
            file.write_text('class Settings:\n    value = 2\n    if value == 2:\n        enabled = True\n')
            result = analyze(str(file))
            output = generate(result, result.candidates)
            namespace = {}
            with patch.dict(os.environ, {'JEV_ENABLED': '0'}):
                exec(compile((output / file.name).read_bytes(), 'generated', 'exec'), namespace)
            self.assertTrue(namespace['Settings'].enabled)
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / 'main.py'
            file.write_text('if (a if b else c):\n    pass\n')
            result = analyze(str(file))
            # An unsupported outer expression is skipped; inner simple test is proposed.
            self.assertEqual(len(result.candidates), 1)

    def test_failed_generation_cleans_stage(self):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / 'main.py'
            file.write_text('if text == "urgent":\n    pass\n')
            result = analyze(str(file))
            result.candidates[0].question = ''
            with self.assertRaises(ValueError):
                generate(result, result.candidates)
            self.assertFalse(result.output.exists())
            self.assertEqual(list(Path(temporary).glob('.jev-*')), [])

    def test_project_roundtrip_and_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / '한글 project'
            root.mkdir()
            code = '"""doc"""\nfrom __future__ import annotations\ndef route(text):\n    if text == "urgent":\n        return "fast"\n    return "normal"\n'
            (root / 'main.py').write_text(code, encoding='utf-8')
            (root / 'data.txt').write_text('resource')
            result = analyze(str(root))
            self.assertEqual(len(result.candidates), 1)
            output = generate(result, result.candidates)
            self.assertEqual((root / 'main.py').read_text(encoding='utf-8'), code)
            self.assertEqual((output / 'data.txt').read_text(), 'resource')
            namespace = {}
            with patch.dict(os.environ, {'JEV_ENABLED': '0'}):
                exec(compile((output / 'main.py').read_bytes(), 'generated', 'exec'), namespace)
                self.assertEqual(namespace['route']('urgent'), 'fast')
                self.assertEqual(namespace['route']('hello'), 'normal')
            with self.assertRaises(ValueError):
                generate(result, result.candidates)

    def test_changed_source_and_exclusions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'sample'
            root.mkdir()
            file = root / 'main.py'
            file.write_text('if value == 1:\n    pass\nif check():\n    pass\n')
            result = analyze(str(file))
            self.assertEqual(len(result.candidates), 1)
            file.write_text('if value == 2:\n    pass\n')
            with self.assertRaises(ValueError):
                generate(result, result.candidates)
            self.assertFalse(result.output.exists())

    def test_runtime_payload_and_thresholds(self):
        class Response:
            def __enter__(self):
                import io
                return io.StringIO(json.dumps({'answers': {'decision': {'type': 'noul', 'noul': self.probability}}}))
            def __exit__(self, *args):
                pass
        for probability, expected in [(0.9, True), (0.1, False), (0.5, False)]:
            response = Response()
            response.probability = probability
            with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'fake', 'JEV_ENABLED': '1'}), patch('urllib.request.urlopen', return_value=response) as call:
                self.assertEqual(decide(False, {'text': 'hello'}, 'Is urgent?'), expected)
                payload = json.loads(call.call_args[0][0].data)
                self.assertEqual(payload['questions']['decision']['type'], 'noul')
                self.assertEqual(payload['state'], {'text': 'hello'})
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': 'fake', 'JEV_ENABLED': '1'}), patch('urllib.request.urlopen', side_effect=OSError('offline')):
            with self.assertWarns(RuntimeWarning):
                self.assertTrue(decide(True, {}, 'test'))

    def test_encoding_and_unicode_offsets(self):
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / 'main.py'
            file.write_bytes('# coding: cp949\n이름 = "긴급"\n결과 = 1 if 이름 == "긴급" else 0\n'.encode('cp949'))
            result = analyze(str(file))
            output = generate(result, result.candidates)
            namespace = {}
            with patch.dict(os.environ, {'JEV_ENABLED': '0'}):
                exec(compile((output / 'main.py').read_bytes(), 'generated', 'exec'), namespace)
            self.assertEqual(namespace['결과'], 1)


if __name__ == '__main__':
    unittest.main()
