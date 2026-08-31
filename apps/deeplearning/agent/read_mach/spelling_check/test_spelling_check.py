from dataclasses import dataclass

from spelling_check import check_pages, iter_language_segments, parse_args


@dataclass
class FakeMatch:
    offset: int
    error_length: int
    replacements: list[str]
    message: str = "오타입니다."
    rule_id: str = "FAKE_RULE"


class FakeChecker:
    def check(self, text: str):
        target = "틀린말" if "틀린말" in text else "mispeling" if "mispeling" in text else ""
        return [FakeMatch(text.index(target), len(target), ["수정어"])] if target else []

    def close(self):
        pass


def test_language_segments_check_embedded_english_separately():
    segments = list(iter_language_segments("한글 API 문장입니다. English sentence."))
    assert segments == [
        ("ko-KR", "한글 API 문장입니다."),
        ("en-US", "API"),
        ("en-US", "English sentence."),
    ]


def test_check_pages_reports_page_error_and_correction():
    checker = FakeChecker()
    issues, empty_pages = check_pages(
        ["정상 문장입니다.", "이것은 틀린말 입니다. A mispeling."],
        {"ko-KR": checker, "en-US": checker},
    )
    assert empty_pages == []
    assert [(item.page, item.error, item.correction) for item in issues] == [
        (2, "틀린말", "수정어"),
        (2, "mispeling", "수정어"),
    ]


def test_empty_pdf_page_is_reported():
    checker = FakeChecker()
    issues, empty_pages = check_pages(["", "English text."], {"ko-KR": checker, "en-US": checker})
    assert issues == []
    assert empty_pages == [1]


def test_progress_reports_every_page():
    checker = FakeChecker()
    progress = []
    check_pages(
        ["첫 페이지입니다.", "Second page."],
        {"ko-KR": checker, "en-US": checker},
        progress=lambda current, total: progress.append((current, total)),
    )
    assert progress == [(1, 2), (2, 2)]


def test_public_api_and_remote_url_are_mutually_exclusive():
    try:
        parse_args(["input.pdf", "--public-api", "--remote-url", "http://localhost:8081"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("서버 모드 옵션이 동시에 허용됐습니다.")


def test_korean_only_skips_english_without_checker():
    checker = FakeChecker()
    issues, _ = check_pages(
        ["틀린말 입니다. A mispeling."],
        {"ko-KR": checker},
    )
    assert [(item.language, item.error) for item in issues] == [("ko-KR", "틀린말")]


def test_korean_only_argument():
    args = parse_args(["input.pdf", "--korean-only"])
    assert args.korean_only is True
