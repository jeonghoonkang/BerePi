import asyncio
import base64
import copy
import json
import unittest
from unittest.mock import patch

import sequential_prompt as ocr

PNG = b"\x89PNG\r\n\x1a\nimage-data"
BINARY = b"\x00\xffbinary"


def request(content="첨부 파일 OCR 해주세요", data=PNG, name="scan.bin"):
    return {"model": "google/gemma-4-31b-it", "stream": True, "temperature": 0.1,
            "messages": [{"role": "user", "content": content}],
            "files": [{"name": name, "content_base64": base64.b64encode(data).decode()}]}


class RequestTests(unittest.TestCase):
    def test_korean_default_preserves_history_options_and_existing_system(self):
        for content in ('Answer concisely.', [{'type': 'text', 'text': 'Answer concisely.'}]):
            incoming = {'stream': True, 'temperature': 0.3, 'messages': [
                {'role': 'system', 'content': content},
                {'role': 'user', 'content': 'earlier'},
                {'role': 'assistant', 'content': 'earlier answer'},
                {'role': 'user', 'content': 'Answer in English please'}]}
            original = copy.deepcopy(incoming)
            result = ocr.prepare_chat_request(incoming)
            self.assertEqual(incoming, original)
            self.assertIn(ocr.DEFAULT_RESPONSE_SYSTEM_PROMPT, str(result['messages'][0]))
            self.assertIn('Answer concisely.', str(result['messages'][0]))
            self.assertEqual(result['messages'][1:], incoming['messages'][1:])
            self.assertTrue(result['stream'])
            self.assertEqual(result['temperature'], 0.3)
            self.assertEqual(ocr.prepare_chat_request(result), result)

    def test_explicit_modes_drop_previous_image_and_conversation(self):
        for phrase, system in (("ocr please", ocr.OCR_SYSTEM_PROMPT),
                               ("explain please", ocr.EXPLAIN_SYSTEM_PROMPT),
                               ("please explain this photo", ocr.EXPLAIN_SYSTEM_PROMPT)):
            incoming = request(content=phrase)
            incoming['messages'][:0] = [
                {'role': 'system', 'content': 'Be precise.'},
                {'role': 'user', 'content': 'old image'},
                {'role': 'assistant', 'content': 'old neural network explanation'}]
            with self.subTest(phrase=phrase):
                result = ocr.prepare_chat_request(incoming)
                self.assertEqual(len(result['messages']), 2)
                self.assertIn(system, result['messages'][0]['content'])
                self.assertEqual(result['messages'][1]['content'][0]['text'], phrase)
                self.assertEqual(ocr.prepare_chat_request(result), result)

    def test_explain_native_image_and_negative_or_text_only(self):
        incoming = {'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': 'explain please'},
            {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64.b64encode(PNG).decode()}}]}]}
        result = ocr.prepare_chat_request(incoming)
        self.assertEqual(result['messages'][0]['content'], ocr.EXPLAIN_SYSTEM_PROMPT)
        self.assertEqual(result['messages'][1], incoming['messages'][0])
        for phrase in ('do not explain please', 'hello'):
            self.assertEqual(ocr.prepare_chat_request(request(content=phrase))['messages'][0]['content'], ocr.DEFAULT_RESPONSE_SYSTEM_PROMPT)
        plain = {'messages': [{'role': 'user', 'content': 'explain please'}]}
        self.assertEqual(ocr.prepare_chat_request(plain)["messages"][0]["content"], ocr.DEFAULT_RESPONSE_SYSTEM_PROMPT)

    def test_image_bytes_and_request_enter_same_vllm_payload(self):
        incoming = request()
        original = copy.deepcopy(incoming)
        result = ocr.prepare_chat_request(incoming)
        self.assertEqual(incoming, original)
        self.assertEqual(result["messages"][0], {"role": "system", "content": ocr.OCR_SYSTEM_PROMPT})
        self.assertTrue(result["messages"][1]["content"][-1]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertNotIn("files", result)
        self.assertTrue(result["stream"])
        self.assertEqual(result["temperature"], 0.1)

    def test_binary_sent_as_data_and_system_is_preserved(self):
        incoming = request(data=BINARY)
        incoming["messages"].insert(0, {"role": "system", "content": "Answer in Korean."})
        result = ocr.prepare_chat_request(incoming)
        self.assertEqual(len(result["messages"]), 2)
        self.assertTrue(result["messages"][0]["content"].startswith("Answer in Korean."))
        self.assertIn(ocr.OCR_SYSTEM_PROMPT, result["messages"][0]["content"])
        self.assertIn(base64.b64encode(BINARY).decode(), result["messages"][1]["content"][-1]["text"])
        self.assertNotIn("image_url", str(result))
        self.assertEqual(ocr.prepare_chat_request(result), result)

    def test_negative_and_unspecified_requests_do_not_inject_system(self):
        for text in ("파일을 설명해 주세요", "OCR 하지 마세요", "OCR 없이 요약", "do not run OCR"):
            result = ocr.prepare_chat_request(request(content=text))
            self.assertEqual(result["messages"][0]["content"], ocr.DEFAULT_RESPONSE_SYSTEM_PROMPT)

    def test_only_latest_user_text_can_enable_ocr(self):
        incoming = request(content="설명해주세요", data="OCR 해주세요".encode(), name="OCR 해주세요.png")
        incoming["messages"].insert(0, {"role": "user", "content": "OCR 해주세요"})
        result = ocr.prepare_chat_request(incoming)
        self.assertNotIn(ocr.OCR_SYSTEM_PROMPT, str(result["messages"]))
        plain = {"messages": [{"role": "user", "content": "OCR 해주세요"}]}
        self.assertEqual(ocr.prepare_chat_request(plain)["messages"][0]["content"], ocr.DEFAULT_RESPONSE_SYSTEM_PROMPT)

    def test_native_image_content_and_system_text_parts(self):
        incoming = {"messages": [
            {"role": "system", "content": [{"type": "text", "text": "Be precise."}]},
            {"role": "user", "content": [{"type": "text", "text": "OCR 실행해 주세요"},
                {"type": "image_url", "image_url": {"url": "https://example.com/scan.png"}}]}]}
        result = ocr.prepare_chat_request(incoming)
        self.assertEqual(result["messages"][0]["content"][-1]["text"], ocr.OCR_SYSTEM_PROMPT)
        self.assertEqual(result["messages"][1], incoming["messages"][1])

    def test_native_pdf_file_part_is_rendered_to_images(self):
        incoming = {"messages": [{"role": "user", "content": [
            {"type": "text", "text": "OCR 해주세요"},
            {"type": "file", "file": {"filename": "scan.pdf", "file_data":
                "data:application/pdf;base64," + base64.b64encode(b"%PDF-1.4\n").decode()}}]}]}
        with patch.object(ocr, "pdf_images", return_value=[base64.b64encode(PNG).decode()]) as render:
            result = ocr.prepare_chat_request(incoming)
        render.assert_called_once_with(b"%PDF-1.4\n")
        self.assertEqual(result["messages"][1]["content"][-1]["type"], "image_url")
        self.assertNotIn('"type": "file"', json.dumps(result))

    def test_ocr_request_can_ask_to_avoid_summarization(self):
        result = ocr.prepare_chat_request(request(content="요약하지 말고 OCR 해주세요"))
        self.assertEqual(result["messages"][0]["content"], ocr.OCR_SYSTEM_PROMPT)

    def test_invalid_files_are_rejected(self):
        for files in ("bad", [None], [{"name": "bad", "content_base64": "!!!"}]):
            incoming = request()
            incoming["files"] = files
            with self.assertRaises(ValueError):
                ocr.prepare_chat_request(incoming)


class MiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def call_middleware(self, raw, path="/v1/chat/completions"):
        self.forwarded = None
        self.events = []
        scope = {"type": "http", "method": "POST", "path": path,
                 "headers": [(b"authorization", b"Bearer test"),
                             (b"content-length", str(len(raw)).encode())]}
        split = len(raw) // 2
        requests = [{"type": "http.request", "body": raw[:split], "more_body": True},
                    {"type": "http.request", "body": raw[split:], "more_body": False}]

        async def receive():
            return requests.pop(0) if requests else {"type": "http.disconnect"}

        async def app(scope, receive, send):
            if path == "/v1/chat/completions":
                event = await receive()
                self.forwarded = (scope, event)
                self.assertEqual((await receive())["type"], "http.disconnect")
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", b"text/event-stream")]})
            await send({"type": "http.response.body", "body": b"data: chunk1\n\n", "more_body": True})
            await send({"type": "http.response.body", "body": b"data: [DONE]\n\n", "more_body": False})

        async def send(event):
            self.events.append(event)

        await ocr.OCRPromptMiddleware(app)(scope, receive, send)

    async def test_asgi_rewrites_chunked_body_and_preserves_stream(self):
        await self.call_middleware(json.dumps(request(data=BINARY)).encode())
        scope, event = self.forwarded
        self.assertEqual(int(dict(scope["headers"])[b"content-length"]), len(event["body"]))
        self.assertEqual(dict(scope["headers"])[b"authorization"], b"Bearer test")
        self.assertEqual(json.loads(event["body"])["messages"][0]["content"], ocr.OCR_SYSTEM_PROMPT)
        self.assertEqual(self.events[-2]["body"], b"data: chunk1\n\n")
        self.assertEqual(self.events[-1]["body"], b"data: [DONE]\n\n")

    async def test_malformed_request_returns_400_without_model_call(self):
        await self.call_middleware(b"not json")
        self.assertIsNone(self.forwarded)
        self.assertEqual(self.events[0]["status"], 400)
        self.assertEqual(json.loads(self.events[1]["body"])["error"]["type"], "invalid_request_error")

    async def test_other_endpoints_pass_through(self):
        await self.call_middleware(b"unchanged", path="/health")
        self.assertEqual(self.events[0]["status"], 200)


if __name__ == "__main__":
    unittest.main()
