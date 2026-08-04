from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bizcard_text_extractor import (
    CardImage,
    _webdav_image_urls,
    bizcard_markdown,
    parse_bizcard_response,
    process_cards,
    render_bizcard_document,
    save_webdav_cards,
)


class BizcardTextExtractorTests(unittest.TestCase):
    def test_parses_fenced_model_json_and_normalizes_lists(self) -> None:
        result = parse_bizcard_response(
            '```json\n{"name":"홍길동","company":"KETI","email":"a@example.com","raw_text":"홍길동"}\n```'
        )
        self.assertEqual(result["name"], "홍길동")
        self.assertEqual(result["email"], ["a@example.com"])
        self.assertEqual(result["phone"], [])

    def test_creates_readable_markdown(self) -> None:
        card = parse_bizcard_response('{"name":"홍길동","mobile":["010-1234-5678"]}')
        document = bizcard_markdown(card, "input/card.jpg")
        self.assertIn("# 명함 - 홍길동", document)
        self.assertIn("010-1234-5678", document)
        self.assertIn("원본: input/card.jpg", document)

    def test_combined_document_has_index_before_card_contents(self) -> None:
        card = parse_bizcard_response('{"name":"홍길동","company":"KETI"}')
        document = render_bizcard_document([{"source": "input/card.jpg", "card": card}])
        self.assertLess(document.index("## Index"), document.index("## 명함 - 홍길동"))
        self.assertIn("[홍길동 — KETI](#bizcard-1)", document)

    def test_reads_webdav_image_members_only(self) -> None:
        xml = b'''<d:multistatus xmlns:d="DAV:">
          <d:response><d:href>/cards/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>
          <d:response><d:href>/cards/a.jpg</d:href><d:propstat><d:prop><d:resourcetype/></d:prop></d:propstat></d:response>
          <d:response><d:href>/cards/note.txt</d:href><d:propstat><d:prop><d:resourcetype/></d:prop></d:propstat></d:response>
        </d:multistatus>'''
        self.assertEqual(_webdav_image_urls(xml, "https://dav.example/cards"), ["https://dav.example/cards/a.jpg"])

    def test_saves_webdav_cards_and_disambiguates_duplicate_names(self) -> None:
        cards = [
            CardImage("card.jpg", "https://dav.example/a/card.jpg", b"first"),
            CardImage("card.jpg", "https://dav.example/b/card.jpg", b"second"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            saved = save_webdav_cards(cards, Path(directory))
            self.assertEqual([path.name for path in saved], ["card.jpg", "card_2.jpg"])
            self.assertEqual(saved[0].read_bytes(), b"first")
            self.assertEqual(saved[1].read_bytes(), b"second")

    @patch("bizcard_text_extractor.call_vision_ocr")
    def test_writes_one_markdown_and_state(self, call_model) -> None:
        call_model.return_value = ('{"name":"홍길동","company":"KETI"}', {"ocr_model": "test"})
        image = CardImage("card.jpg", "input/card.jpg", b"\xff\xd8\xffdata")
        with tempfile.TemporaryDirectory() as directory:
            results = process_cards(
                [image], config_path=Path("config.json"), output_dir=Path(directory)
            )
            markdown_files = list(Path(directory).glob("*.md"))
            self.assertEqual([path.name for path in markdown_files], ["bizcards.md"])
            self.assertTrue((Path(directory) / ".bizcard_state.json").is_file())
            self.assertEqual(results[0]["source"], "input/card.jpg")

    @patch("bizcard_text_extractor.call_vision_ocr")
    def test_skips_processed_source_unless_forced(self, call_model) -> None:
        call_model.return_value = ('{"name":"홍길동"}', {"ocr_model": "test"})
        image = CardImage("card.jpg", "input/card.jpg", b"\xff\xd8\xffdata")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = process_cards([image], config_path=Path("config.json"), output_dir=output)
            skipped = process_cards([image], config_path=Path("config.json"), output_dir=output)
            forced = process_cards(
                [image], config_path=Path("config.json"), output_dir=output, force=True
            )
            state = (output / ".bizcard_state.json").read_text(encoding="utf-8")
        self.assertEqual(len(first), 1)
        self.assertEqual(skipped, [])
        self.assertEqual(len(forced), 1)
        self.assertEqual(call_model.call_count, 2)
        self.assertEqual(state.count('"source": "input/card.jpg"'), 1)


if __name__ == "__main__":
    unittest.main()
