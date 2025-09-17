from http.server import SimpleHTTPRequestHandler
import socketserver
from pathlib import Path

PORT = 8000
ROOT = Path(__file__).resolve().parent

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)


if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving LLM QA Web at http://localhost:{PORT}/")
        httpd.serve_forever()
