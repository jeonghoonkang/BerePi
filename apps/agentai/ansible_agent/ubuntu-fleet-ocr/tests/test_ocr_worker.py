from __future__ import annotations

import importlib.util
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = (
    Path(__file__).parents[1]
    / "roles"
    / "sononet_edge"
    / "files"
    / "ocr_worker.py"
)
SPEC = importlib.util.spec_from_file_location("ocr_worker", MODULE_PATH)
assert SPEC and SPEC.loader
OCR_WORKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OCR_WORKER)


class OcrWorkerTest(unittest.TestCase):
    def test_processes_each_image_hash_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "sync" / "inbox" / "sample.jpg"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"fake-image-for-mocked-api")
            old = time.time() - 120
            os.utime(image, (old, old))
            settings = {
                "SONONET_DEVICE_ID": "TEST-001",
                "NEXTCLOUD_LOCAL_DIR": str(root / "sync"),
                "OCR_API_BASE_URL": "http://127.0.0.1:8000",
                "OCR_API_KEY": "test-key",
                "OCR_MODEL": "google/gemma-4-31B-it",
                "OCR_STATE_DB": str(root / "state.sqlite3"),
                "OCR_STABLE_AGE_SECONDS": "30",
            }
            mocked_response = ("테스트 OCR", {"usage": {"completion_tokens": 3}})
            with mock.patch.dict(os.environ, settings, clear=True), mock.patch.object(
                OCR_WORKER, "request_ocr", return_value=mocked_response
            ) as request_ocr:
                self.assertEqual(OCR_WORKER.main(), 0)
                self.assertEqual(OCR_WORKER.main(), 0)

            self.assertEqual(request_ocr.call_count, 1)
            result = root / "sync" / "ocr-results" / "sample.jpg.ocr.txt"
            self.assertEqual(result.read_text(encoding="utf-8"), "테스트 OCR\n")


if __name__ == "__main__":
    unittest.main()
