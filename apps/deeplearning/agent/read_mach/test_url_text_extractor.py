from __future__ import annotations

import unittest

from url_text_extractor import extract_article_text, output_stem_for_url, validate_url


class UrlTextExtractorTests(unittest.TestCase):
    def test_extracts_article_without_navigation_or_script(self) -> None:
        html = """
        <html><head><title>Physical AI 전망</title><link rel="canonical" href="https://example.test/article"></head>
        <body><nav>메뉴 문구</nav><article><h1>데이터센터 인프라</h1>
        <p>Physical AI를 위한 고성능 인프라를 설명합니다.</p>
        <ul><li>GPU 컴퓨팅</li><li>고속 네트워크</li></ul>
        <script>secret()</script></article></body></html>
        """

        text, metadata = extract_article_text(html, "https://example.test/original")

        self.assertIn("데이터센터 인프라", text)
        self.assertIn("- GPU 컴퓨팅", text)
        self.assertNotIn("메뉴 문구", text)
        self.assertNotIn("secret", text)
        self.assertEqual(metadata["canonical_url"], "https://example.test/article")

    def test_rejects_non_http_url(self) -> None:
        with self.assertRaises(ValueError):
            validate_url("file:///etc/passwd")

    def test_uses_open_graph_title_when_html_title_is_missing(self) -> None:
        html = '<html><head><meta property="og:title" content="Cloud 기술"></head><body><main><p>본문 문자가 충분히 들어 있는 테스트 페이지입니다.</p></main></body></html>'
        text, metadata = extract_article_text(html, "https://example.test/cloud")
        self.assertEqual(metadata["title"], "Cloud 기술")
        self.assertIn("# Cloud 기술", text)

    def test_output_name_is_stable_and_safe(self) -> None:
        first = output_stem_for_url("https://example.test/entry/한글 제목")
        second = output_stem_for_url("https://example.test/entry/한글 제목")
        self.assertEqual(first, second)
        self.assertNotIn(" ", first)


if __name__ == "__main__":
    unittest.main()
