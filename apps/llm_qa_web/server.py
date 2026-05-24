import json
import os
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler
import socketserver
from pathlib import Path

PORT = int(os.environ.get("PORT", "8000"))
ROOT = Path(__file__).resolve().parent
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")


def get_openai_api_key():
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return api_key

    for path in (ROOT / "nocommit_key.txt", ROOT.parent / "nocommit_key.txt"):
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()

    return None


def ask_openai(prompt):
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경 변수를 설정하세요.")

    payload = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        if self.path != "/api/ask":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body or "{}")
            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                self.send_json({"error": "prompt는 비어 있을 수 없습니다."}, HTTPStatus.BAD_REQUEST)
                return

            answer = ask_openai(prompt)
            self.send_json({"model": OPENAI_MODEL, "prompt": prompt, "answer": answer})
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            self.send_json({"error": detail}, exc.code)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def send_json(self, payload, status=HTTPStatus.OK):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving LLM QA Web at http://localhost:{PORT}/")
        httpd.serve_forever()
