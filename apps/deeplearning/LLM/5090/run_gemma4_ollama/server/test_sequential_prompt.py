import base64
import json
import shutil
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

import sequential_prompt as sequential
import server


def encoded(value):
    return base64.b64encode(value).decode("ascii")


class AttachmentTests(unittest.TestCase):
    def test_content_signature_overrides_extension(self):
        for name, content, kind in [
            ("fake.bin", b"%PDF-1.4\n", "pdf"),
            ("fake.pdf", b"\x89PNG\r\n\x1a\nrest", "image"),
            ("fake.jpg", b"\x00\xffbinary", "binary"),
            ("memo.txt", "한글 메모".encode(), "text"),
        ]:
            self.assertEqual(sequential.detect_attachment(name, content).kind, kind)

    def test_only_explicit_affirmation_enables_ocr(self):
        for reply in (None, False, "", "아니요", "OCR 하지 마세요", "no ocr", "yes but don't OCR"):
            self.assertFalse(sequential.ocr_requested(reply), reply)
        for reply in (True, "OCR 실행", "OCR 해주세요", "네", "yes", "run OCR"):
            self.assertTrue(sequential.ocr_requested(reply), reply)

    def test_initial_ocr_instruction_embedded_in_prompt(self):
        for prompt in ("ocr 해주세요", "첨부 파일에 대해 OCR 해 주세요.",
                       "이 바이너리 파일 OCR을 실행해 주세요", "스캔 문서 OCR 처리해주세요",
                       "Please perform OCR on this file", "Run OCR on the attachment"):
            self.assertTrue(sequential.initial_ocr_requested(prompt), prompt)
        for prompt in ("이 파일을 확인해 주세요", "yes", "ocr이 뭔가요?",
                       "OCR 하지 마세요", "OCR 없이 요약해주세요", "do not run OCR",
                       "OCR 해주세요. 아니요, 하지 마세요", "OCR 안 해도 됩니다"):
            self.assertFalse(sequential.initial_ocr_requested(prompt), prompt)

    def test_invalid_payloads_are_rejected(self):
        for request in ({"files": "bad"}, {"images": "bad"},
                        {"files": [None]}, {"images": ["not base64!"]},
                        {"images": [encoded(b"a")] * 11}):
            with self.assertRaises(ValueError):
                sequential.attachments_from_request(request)

    def test_image_and_binary_reach_distinct_model_inputs(self):
        image = sequential.detect_attachment("test.png", b"\x89PNG\r\n\x1a\ncontent")
        binary = sequential.detect_attachment("test.bin", b"\x00\xffcontent")
        fields = sequential.model_attachment_fields([image, binary], "아니요")
        self.assertEqual(fields["images"], [encoded(image.content)])
        self.assertIn(encoded(binary.content), fields["attachment_text"])
        self.assertNotIn("system", fields)
        self.assertEqual(sequential.model_attachment_fields([image], "yes")["system"],
                         sequential.OCR_SYSTEM_PROMPT)

    def test_pdf_uses_rendered_pages_for_both_choices(self):
        pdf = sequential.detect_attachment("scan.pdf", b"%PDF-1.4\n")
        with patch.object(sequential, "pdf_images", return_value=["page1", "page2"]) as render:
            for reply in ("yes", "no"):
                self.assertEqual(sequential.model_attachment_fields([pdf], reply)["images"],
                                 ["page1", "page2"])
            self.assertEqual(render.call_count, 2)
        with patch.object(sequential.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, "Poppler"):
                sequential.pdf_images(pdf.content)

    @unittest.skipUnless(shutil.which("pdftoppm"), "Poppler is not installed")
    def test_actual_pdf_rasterization(self):
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] /Contents 4 0 R >>",
            b"<< /Length 0 >>\nstream\n\nendstream",
        ]
        pdf = b"%PDF-1.4\n"
        offsets = [0]
        for index, obj in enumerate(objects, 1):
            offsets.append(len(pdf))
            pdf += str(index).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
        xref = len(pdf)
        pdf += b"xref\n0 5\n0000000000 65535 f \n"
        for offset in offsets[1:]:
            pdf += f"{offset:010d} 00000 n \n".encode()
        pdf += f"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        pages = sequential.pdf_images(pdf)
        self.assertEqual(len(pages), 1)
        self.assertTrue(base64.b64decode(pages[0]).startswith(b"\x89PNG\r\n\x1a\n"))
        with patch.object(sequential, "MAX_PDF_PAGES", 0):
            with self.assertRaises(ValueError):
                sequential.pdf_images(pdf)

    def test_ocr_system_reaches_ollama_without_internal_metadata(self):
        with (patch.object(server, "request_json", return_value={"response": "text"}) as request,
              patch.object(server, "read_selected_gpu", return_value="auto"),
              patch.object(server, "list_gpus", return_value=([], "")),
              patch.object(server, "server_ip", return_value="127.0.0.1")):
            server.run_ollama_generate(server.prompt_payload_for_execution({
                "model": "vision-model", "prompt": "read", "images": ["encoded-image"],
                "system": sequential.OCR_SYSTEM_PROMPT, "_attachment_text": "file data",
            }))
        payload = request.call_args.kwargs["payload"]
        self.assertEqual(payload["system"], server.DEFAULT_RESPONSE_SYSTEM_PROMPT + "\n\n" + sequential.OCR_SYSTEM_PROMPT)
        self.assertEqual(payload["images"], ["encoded-image"])
        self.assertEqual(payload["prompt"], "read\n\nfile data")
        self.assertNotIn("_attachment_text", payload)

    def test_default_korean_system_reaches_ollama_without_mutating_request(self):
        original = {"model": "model", "prompt": "hello"}
        with (patch.object(server, "request_json", return_value={"response": "안녕하세요"}) as request,
              patch.object(server, "read_selected_gpu", return_value="auto"),
              patch.object(server, "list_gpus", return_value=([], "")),
              patch.object(server, "server_ip", return_value="127.0.0.1")):
            server.run_ollama_generate(original)
        self.assertEqual(request.call_args.kwargs["payload"]["system"], server.DEFAULT_RESPONSE_SYSTEM_PROMPT)
        self.assertNotIn("system", original)

    def test_ocr_excludes_history_and_preserves_current_attachment(self):
        payload = {"prompt": "question", "_history_user_prompt": "question",
                   "_remember_history": True, "_attachment_text": "binary payload",
                   "system": sequential.OCR_SYSTEM_PROMPT, "images": ["current-image"]}
        with patch.object(server, "read_conversation_history", return_value=[
                {"role": "assistant", "content": "previous answer"}]):
            execution = server.prompt_payload_for_execution(payload)
        self.assertEqual(execution["prompt"], "question\n\nbinary payload")
        self.assertEqual(execution["images"], ["current-image"])
        self.assertEqual(payload["_history_user_prompt"], "question")
        self.assertEqual(execution["system"], sequential.OCR_SYSTEM_PROMPT)


class AttachmentHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class QuietHandler(server.Gemma4Handler):
            def log_message(self, *args):
                pass

            def remember_access(self, *args):
                pass

        cls.httpd = server.Gemma4ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.httpd.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def post(self, payload, endpoint="/api/generate"):
        request = urllib.request.Request(self.url + endpoint, data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.load(response)

    def test_confirmation_then_yes_no_empty_and_async_requests(self):
        files = [{"name": "scan.png", "content_base64": encoded(b"\x89PNG\r\n\x1a\ndata")}]
        with (patch.object(server, "is_authorized_user", return_value=True),
              patch.object(server, "remember_prompts"), patch.object(server, "remember_user_prompt"),
              patch.object(server, "request_options", return_value={}),
              patch.object(server, "run_queued_prompt", return_value={"response": "ok"}) as run,
              patch.object(server, "enqueue_prompt_job") as enqueue,
              patch.object(server, "queued_prompt_ack", return_value={"queued": True})):
            result = self.post({"files": files})
            self.assertTrue(result["ocr_confirmation_required"])
            self.assertEqual(result["attachments"][0]["kind"], "image")
            run.assert_not_called()
            enqueue.assert_not_called()
            for reply in ("OCR 실행", "아니요", "", None):
                result = self.post({"files": files, "ocr_reply": reply})
                payload = run.call_args.args[0]
                self.assertEqual(payload["images"], [files[0]["content_base64"]])
                self.assertEqual("system" in payload, reply == "OCR 실행")
                self.assertEqual(result["ocr_enabled"], reply == "OCR 실행")
            self.post({"files": files, "ocr_reply": True}, "/api/enqueue-generate")
            self.assertIn("system", enqueue.call_args.args[0])

    def test_explain_photo_uses_current_image_without_history(self):
        from pathlib import Path
        photo = Path(__file__).resolve().parents[5] / 'photo_browser/sample_pics/IMG_6735.JPG'
        if not photo.exists():
            self.skipTest('Sample photo is not available')
        image = encoded(photo.read_bytes())
        files = [{"name": photo.name, "content_base64": image}]
        with (patch.object(server, "is_authorized_user", return_value=True),
              patch.object(server, "remember_prompts"), patch.object(server, "remember_user_prompt"),
              patch.object(server, "request_options", return_value={}),
              patch.object(server, "run_queued_prompt", return_value={"response": "test response"}) as run,
              patch.object(server, "read_conversation_history") as history):
            result = self.post({"files": files, "prompt": "explain please"})
            self.assertTrue(result['explain_enabled'])
            self.assertFalse(result['ocr_enabled'])
            payload = server.prompt_payload_for_execution(run.call_args.args[0])
            self.assertEqual(payload['images'], [image])
            self.assertEqual(payload['system'], sequential.EXPLAIN_SYSTEM_PROMPT)
            self.assertEqual(payload['prompt'], 'explain please')
            history.assert_not_called()

    def test_explain_phrase_detection(self):
        for text in ('explain please', 'Please explain this photo', 'EXPLAIN PLEASE'):
            self.assertTrue(sequential.initial_explain_requested(text))
        for text in ('do not explain please', 'ocr please', 'hello'):
            self.assertFalse(sequential.initial_explain_requested(text))

    def test_initial_ocr_request_skips_confirmation_and_respects_explicit_reply(self):
        files = [{"name": "data.bin", "content_base64": encoded(b"\x00\xffdata")}]
        with (patch.object(server, "is_authorized_user", return_value=True),
              patch.object(server, "remember_prompts"), patch.object(server, "remember_user_prompt"),
              patch.object(server, "request_options", return_value={}),
              patch.object(server, "run_queued_prompt", return_value={"response": "ok"}) as run,
              patch.object(server, "enqueue_prompt_job") as enqueue,
              patch.object(server, "queued_prompt_ack", return_value={"queued": True})):
            result = self.post({"files": files, "prompt": "첨부한 바이너리 파일 OCR 해주세요"})
            self.assertTrue(result["ocr_enabled"])
            self.assertNotIn("ocr_confirmation_required", result)
            self.assertEqual(run.call_args.args[0]["system"], sequential.OCR_SYSTEM_PROMPT)
            self.assertIn(encoded(b"\x00\xffdata"), run.call_args.args[0]["_attachment_text"])
            self.post({"files": files, "prompts": ["첨부 파일입니다", "ocr 해주세요"]},
                      "/api/enqueue-generate")
            self.assertEqual(enqueue.call_args.args[0]["system"], sequential.OCR_SYSTEM_PROMPT)
            self.post({"files": files, "prompt": "ocr 해주세요", "ocr_reply": False})
            self.assertNotIn("system", run.call_args.args[0])
            result = self.post({"files": files, "prompt": "OCR 하지 마세요"})
            self.assertTrue(result["ocr_confirmation_required"])

    def test_binary_and_legacy_images_and_text_only(self):
        with (patch.object(server, "is_authorized_user", return_value=True),
              patch.object(server, "remember_prompts"), patch.object(server, "remember_user_prompt"),
              patch.object(server, "request_options", return_value={}),
              patch.object(server, "run_queued_prompt", return_value={"response": "ok"}) as run):
            response = self.post({"images": [encoded(b"\x89PNG\r\n\x1a\ndata")], "prompt": "look"})
            self.assertTrue(response["ocr_confirmation_required"])
            self.post({"prompt": "inspect", "ocr_reply": False, "files": [
                {"name": "data.bin", "content_base64": encoded(b"\x00\xffdata")}]})
            payload = run.call_args.args[0]
            self.assertNotIn("images", payload)
            self.assertIn(encoded(b"\x00\xffdata"), payload["_attachment_text"])
            self.post({"prompt": "hello"})
            self.assertEqual(run.call_args.args[0]["prompt"], "hello")
            self.assertNotIn("system", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
