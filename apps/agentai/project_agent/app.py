from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import secrets
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from extract import extract_file, write_markdown_record


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
EXTRACTED_MD_DIR = DATA_DIR / "extracted_md"
DB_PATH = DATA_DIR / "project_agent.sqlite3"
CONFIG_PATH = DATA_DIR / "config.json"
PROJECT_MD_PATH = DATA_DIR / "project.md"
SCHEDULE_MD_PATH = DATA_DIR / "schedule.md"
TODO_MD_PATH = DATA_DIR / "todos.md"
STATIC_DIR = BASE_DIR / "static"

APP_TITLE = "Project Agent"
SESSION_TTL_SECONDS = 60 * 60 * 12
DEFAULT_LLM_BASE_URL = os.environ.get("PROJECT_AGENT_LLM_BASE_URL", "http://127.0.0.1:8082").rstrip("/")
DEFAULT_LLM_GENERATE_PATH = os.environ.get("PROJECT_AGENT_LLM_GENERATE_PATH", "/api/generate")
DEFAULT_LLM_MODEL = os.environ.get("PROJECT_AGENT_LLM_MODEL", "gemma4:31b")
DEFAULT_LLM_TIMEOUT_SECONDS = float(os.environ.get("PROJECT_AGENT_LLM_TIMEOUT_SECONDS", "30"))


def ensure_storage() -> None:
    for directory in (DATA_DIR, UPLOAD_DIR, EXTRACTED_MD_DIR, STATIC_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    if not PROJECT_MD_PATH.exists():
        PROJECT_MD_PATH.write_text(
            "# Project Agent\n\n"
            "- Project name: Project Agent\n"
            "- Owner: \n"
            "- Status: planning\n"
            "- Storage: data/uploads\n",
            encoding="utf-8",
        )
    if not SCHEDULE_MD_PATH.exists():
        SCHEDULE_MD_PATH.write_text(
            "# Schedule\n\n"
            "- 2026-06-12: Initial project workspace\n",
            encoding="utf-8",
        )
    if not TODO_MD_PATH.exists():
        TODO_MD_PATH.write_text(
            "# Todos\n\n"
            "- [ ] Upload project files\n"
            "- [ ] Review extracted file records\n"
            "- [ ] Add project schedule details\n",
            encoding="utf-8",
        )
    init_db()


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                author TEXT,
                content TEXT,
                mime_type TEXT,
                file_size INTEGER,
                sha256 TEXT,
                md_path TEXT,
                uploaded_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS file_search USING fts5(
                file_name,
                author,
                content,
                content='files',
                content_rowid='id'
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                list_name TEXT NOT NULL DEFAULT 'todo',
                assignee TEXT,
                labels TEXT,
                due_date TEXT,
                attachment_file_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (attachment_file_id) REFERENCES files(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS card_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL,
                author TEXT,
                comment TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS card_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL,
                worker_name TEXT NOT NULL,
                confirmed_by TEXT,
                source TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(card_id, worker_name),
                FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
            )
            """
        )
        connection.commit()


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        secret = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
        return {"secret": secret, "password": None}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(config: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def has_password() -> bool:
    return bool(load_config().get("password"))


def hash_password(password: str, salt: bytes | None = None) -> dict[str, str]:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 250000)
    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
        "iterations": "250000",
    }


def verify_password(password: str) -> bool:
    config = load_config()
    record = config.get("password")
    if not record:
        return False
    salt = base64.b64decode(record["salt"])
    iterations = int(record.get("iterations", "250000"))
    expected = base64.b64decode(record["hash"])
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def set_password(password: str) -> None:
    if len(password) < 8:
        raise ValueError("Access password must be at least 8 characters.")
    config = load_config()
    config["password"] = hash_password(password)
    save_config(config)


def make_session() -> str:
    config = load_config()
    secret = config["secret"].encode("utf-8")
    expires = str(int(time.time()) + SESSION_TTL_SECONDS)
    nonce = secrets.token_urlsafe(24)
    payload = f"{expires}:{nonce}"
    signature = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{signature}".encode("utf-8")).decode("ascii")


def verify_session(token: str | None) -> bool:
    if not token:
        return False
    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        expires, nonce, signature = decoded.split(":", 2)
    except Exception:
        return False
    if int(expires) < int(time.time()):
        return False
    payload = f"{expires}:{nonce}"
    secret = load_config()["secret"].encode("utf-8")
    expected = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def parse_multipart(body: bytes, content_type: str) -> tuple[dict[str, str], dict[str, Any] | None]:
    marker = "boundary="
    if marker not in content_type:
        return {}, None
    boundary = content_type.split(marker, 1)[1].strip().strip('"')
    delimiter = b"--" + boundary.encode("utf-8")
    fields: dict[str, str] = {}
    file_info: dict[str, Any] | None = None
    for part in body.split(delimiter):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        headers_blob, _, payload = part.partition(b"\r\n\r\n")
        headers_text = headers_blob.decode("utf-8", errors="replace")
        payload = payload.rstrip(b"\r\n")
        disposition = ""
        for line in headers_text.splitlines():
            if line.lower().startswith("content-disposition:"):
                disposition = line
                break
        name = _header_value(disposition, "name")
        filename = _header_value(disposition, "filename")
        if filename:
            file_info = {"field": name, "filename": Path(filename).name, "content": payload}
        elif name:
            fields[name] = payload.decode("utf-8", errors="replace")
    return fields, file_info


def _header_value(header: str, key: str) -> str:
    pattern = f'{key}="'
    if pattern not in header:
        return ""
    return header.split(pattern, 1)[1].split('"', 1)[0]


def store_upload(filename: str, content: bytes, author: str) -> None:
    safe_name = safe_filename(filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = UPLOAD_DIR / f"{timestamp}_{safe_name}"
    target.write_bytes(content)
    document = extract_file(target, author=author)
    md_path = write_markdown_record(document, EXTRACTED_MD_DIR)

    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.execute(
            """
            INSERT INTO files (
                file_name, stored_path, author, content, mime_type, file_size,
                sha256, md_path, uploaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document.file_name,
                document.file_path,
                document.author,
                document.content,
                document.mime_type,
                document.file_size,
                document.sha256,
                str(md_path),
                document.extracted_at,
            ),
        )
        rowid = cursor.lastrowid
        connection.execute(
            "INSERT INTO file_search(rowid, file_name, author, content) VALUES (?, ?, ?, ?)",
            (rowid, document.file_name, document.author, document.content),
        )
        connection.commit()


def safe_filename(filename: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in filename).strip()
    return cleaned or f"upload_{int(time.time())}"


def search_files(query: str = "") -> list[sqlite3.Row]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        if query.strip():
            try:
                return list(
                    connection.execute(
                        """
                        SELECT files.*
                        FROM file_search
                        JOIN files ON files.id = file_search.rowid
                        WHERE file_search MATCH ?
                        ORDER BY rank
                        LIMIT 50
                        """,
                        (query,),
                    )
                )
            except sqlite3.OperationalError:
                like_query = f"%{query}%"
                return list(
                    connection.execute(
                        """
                        SELECT *
                        FROM files
                        WHERE file_name LIKE ? OR author LIKE ? OR content LIKE ?
                        ORDER BY id DESC
                        LIMIT 50
                        """,
                        (like_query, like_query, like_query),
                    )
                )
        return list(connection.execute("SELECT * FROM files ORDER BY id DESC LIMIT 20"))


CARD_LISTS = ("todo", "doing", "done")
CARD_LIST_LABELS = {"todo": "Todo", "doing": "Doing", "done": "Done"}


def create_card(fields: dict[str, list[str]]) -> None:
    title = fields.get("card_title", [""])[0].strip()
    if not title:
        raise ValueError("Card title is required.")
    now = datetime.now().isoformat(timespec="seconds")
    attachment = fields.get("attachment_file_id", [""])[0].strip()
    attachment_id = int(attachment) if attachment.isdigit() else None
    list_name = normalize_card_list(fields.get("list_name", ["todo"])[0])
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO cards (
                title, description, list_name, assignee, labels, due_date,
                attachment_file_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                fields.get("card_description", [""])[0].strip(),
                list_name,
                fields.get("assignee", [""])[0].strip(),
                fields.get("labels", [""])[0].strip(),
                fields.get("due_date", [""])[0].strip(),
                attachment_id,
                now,
                now,
            ),
        )
        connection.commit()


def update_card(fields: dict[str, list[str]]) -> None:
    card_id = int(fields.get("card_id", ["0"])[0])
    now = datetime.now().isoformat(timespec="seconds")
    attachment = fields.get("attachment_file_id", [""])[0].strip()
    attachment_id = int(attachment) if attachment.isdigit() else None
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            UPDATE cards
            SET title = ?, description = ?, list_name = ?, assignee = ?,
                labels = ?, due_date = ?, attachment_file_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                fields.get("card_title", [""])[0].strip(),
                fields.get("card_description", [""])[0].strip(),
                normalize_card_list(fields.get("list_name", ["todo"])[0]),
                fields.get("assignee", [""])[0].strip(),
                fields.get("labels", [""])[0].strip(),
                fields.get("due_date", [""])[0].strip(),
                attachment_id,
                now,
                card_id,
            ),
        )
        connection.commit()


def move_card(fields: dict[str, list[str]]) -> None:
    card_id = int(fields.get("card_id", ["0"])[0])
    list_name = normalize_card_list(fields.get("list_name", ["todo"])[0])
    now = datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("UPDATE cards SET list_name = ?, updated_at = ? WHERE id = ?", (list_name, now, card_id))
        connection.commit()


def delete_card(fields: dict[str, list[str]]) -> None:
    card_id = int(fields.get("card_id", ["0"])[0])
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("DELETE FROM card_comments WHERE card_id = ?", (card_id,))
        connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        connection.commit()


def add_card_comment(fields: dict[str, list[str]]) -> None:
    card_id = int(fields.get("card_id", ["0"])[0])
    comment = fields.get("comment", [""])[0].strip()
    if not comment:
        raise ValueError("Comment is required.")
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO card_comments (card_id, author, comment, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                card_id,
                fields.get("comment_author", [""])[0].strip(),
                comment,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        connection.commit()


def complete_card_worker(fields: dict[str, list[str]], source: str) -> None:
    card_id = int(fields.get("card_id", ["0"])[0])
    worker_name = fields.get("worker_name", [""])[0].strip()
    confirmed_by = fields.get("confirmed_by", [""])[0].strip()
    note = fields.get("completion_note", [""])[0].strip()
    if not worker_name:
        raise ValueError("Worker name is required.")

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO card_completions (
                card_id, worker_name, confirmed_by, source, note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(card_id, worker_name) DO UPDATE SET
                confirmed_by = excluded.confirmed_by,
                source = excluded.source,
                note = excluded.note,
                created_at = excluded.created_at
            """,
            (
                card_id,
                worker_name,
                confirmed_by,
                source,
                note,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        maybe_mark_card_done(connection, card_id)
        connection.commit()


def maybe_mark_card_done(connection: sqlite3.Connection, card_id: int) -> None:
    connection.row_factory = sqlite3.Row
    card = connection.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    if not card:
        return
    workers = parse_workers(card["assignee"])
    if not workers:
        return
    completed = {
        str(row["worker_name"]).strip().lower()
        for row in connection.execute("SELECT worker_name FROM card_completions WHERE card_id = ?", (card_id,))
    }
    if all(worker.lower() in completed for worker in workers):
        connection.execute(
            "UPDATE cards SET list_name = 'done', updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(timespec="seconds"), card_id),
        )


def parse_workers(value: str | None) -> list[str]:
    if not value:
        return []
    parts = []
    for chunk in str(value).replace("\n", ",").replace(";", ",").split(","):
        name = chunk.strip()
        if name and name.lower() not in {item.lower() for item in parts}:
            parts.append(name)
    return parts


def card_completion_rows(card_id: int) -> list[sqlite3.Row]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        return list(
            connection.execute(
                """
                SELECT *
                FROM card_completions
                WHERE card_id = ?
                ORDER BY worker_name
                """,
                (card_id,),
            )
        )


def completion_summary_for_card(card: sqlite3.Row) -> dict[str, Any]:
    workers = parse_workers(card["assignee"])
    completions = card_completion_rows(int(card["id"]))
    completed_by_worker = {str(row["worker_name"]).strip().lower(): row for row in completions}
    completed_count = sum(1 for worker in workers if worker.lower() in completed_by_worker)
    total = len(workers)
    return {
        "workers": workers,
        "completions": completions,
        "completed_by_worker": completed_by_worker,
        "completed_count": completed_count,
        "total": total,
        "done": bool(total and completed_count == total),
    }


def list_cards() -> dict[str, list[sqlite3.Row]]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = list(
            connection.execute(
                """
                SELECT cards.*, files.file_name AS attachment_name, files.stored_path AS attachment_path
                FROM cards
                LEFT JOIN files ON files.id = cards.attachment_file_id
                ORDER BY
                  CASE cards.list_name WHEN 'todo' THEN 1 WHEN 'doing' THEN 2 WHEN 'done' THEN 3 ELSE 4 END,
                  COALESCE(cards.due_date, ''),
                  cards.id DESC
                """
            )
        )
    grouped = {name: [] for name in CARD_LISTS}
    for row in rows:
        grouped.setdefault(normalize_card_list(row["list_name"]), []).append(row)
    return grouped


def recent_card_comments(card_id: int, limit: int = 3) -> list[sqlite3.Row]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        return list(
            connection.execute(
                """
                SELECT *
                FROM card_comments
                WHERE card_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (card_id, limit),
            )
        )


def card_count_by_status() -> dict[str, int]:
    counts = {name: 0 for name in CARD_LISTS}
    with sqlite3.connect(DB_PATH) as connection:
        for list_name, count in connection.execute("SELECT list_name, COUNT(*) FROM cards GROUP BY list_name"):
            counts[normalize_card_list(str(list_name))] = int(count)
    return counts


def uploaded_file_options() -> list[sqlite3.Row]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        return list(connection.execute("SELECT id, file_name FROM files ORDER BY id DESC LIMIT 100"))


def normalize_card_list(value: str) -> str:
    return value if value in CARD_LISTS else "todo"


def read_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def summarize_todos(markdown: str) -> dict[str, int]:
    lines = markdown.splitlines()
    done = sum(1 for line in lines if line.strip().startswith("- [x]"))
    open_count = sum(1 for line in lines if line.strip().startswith("- [ ]"))
    return {"open": open_count, "done": done}


def directory_tree(root: Path, max_depth: int = 3, max_items: int = 160) -> str:
    root = root.resolve()
    lines = [root.name + "/"]
    count = 0

    def walk(directory: Path, prefix: str, depth: int) -> None:
        nonlocal count
        if depth > max_depth or count >= max_items:
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        except OSError:
            return
        for index, entry in enumerate(entries):
            if count >= max_items:
                lines.append(prefix + "...")
                return
            connector = "+-- " if index == len(entries) - 1 else "|-- "
            suffix = "/" if entry.is_dir() else ""
            lines.append(prefix + connector + entry.name + suffix)
            count += 1
            if entry.is_dir():
                child_prefix = prefix + ("    " if index == len(entries) - 1 else "|   ")
                walk(entry, child_prefix, depth + 1)

    walk(root, "", 1)
    return "\n".join(lines)


class ProjectAgentHandler(BaseHTTPRequestHandler):
    server_version = "ProjectAgent/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/static/style.css":
            self.send_static("style.css", "text/css")
            return
        if parsed.path == "/logout":
            self.redirect("/", clear_session=True)
            return
        if not self.is_authenticated():
            self.send_html(render_gate())
            return
        if parsed.path == "/":
            query = parse_qs(parsed.query).get("q", [""])[0]
            self.send_html(render_dashboard(query=query))
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)

        if parsed.path == "/setup":
            fields = parse_qs(body.decode("utf-8", errors="replace"))
            password = fields.get("password", [""])[0]
            try:
                set_password(password)
            except ValueError as exc:
                self.send_html(render_gate(error=str(exc)))
                return
            self.redirect("/", session=make_session())
            return

        if parsed.path == "/login":
            fields = parse_qs(body.decode("utf-8", errors="replace"))
            password = fields.get("password", [""])[0]
            if verify_password(password):
                self.redirect("/", session=make_session())
            else:
                self.send_html(render_gate(error="Access password is incorrect."))
            return

        if not self.is_authenticated():
            self.redirect("/")
            return

        if parsed.path == "/password":
            fields = parse_qs(body.decode("utf-8", errors="replace"))
            current = fields.get("current_password", [""])[0]
            new = fields.get("new_password", [""])[0]
            if not verify_password(current):
                self.send_html(render_dashboard(error="Current password is incorrect."))
                return
            try:
                set_password(new)
            except ValueError as exc:
                self.send_html(render_dashboard(error=str(exc)))
                return
            self.send_html(render_dashboard(message="Access password updated."))
            return

        if parsed.path == "/llm-config":
            fields = parse_qs(body.decode("utf-8", errors="replace"))
            save_llm_config(fields)
            self.send_html(render_dashboard(message="Gemma4 connection settings saved."))
            return

        if parsed.path == "/ask":
            fields = parse_qs(body.decode("utf-8", errors="replace"))
            question = fields.get("question", [""])[0].strip()
            if not question:
                self.send_html(render_dashboard(error="Question is required."))
                return
            prompt = build_project_context(question)
            result = call_gemma4(prompt)
            if result.get("ok"):
                self.send_html(
                    render_dashboard(
                        query=question,
                        message=f"Gemma4 answered with {result.get('model', '')}.",
                        llm_question=question,
                        llm_answer=str(result.get("answer") or ""),
                    )
                )
            else:
                self.send_html(
                    render_dashboard(
                        query=question,
                        error=f"Gemma4 is unavailable, but the site is still usable: {result.get('error')}",
                        llm_question=question,
                        llm_answer="",
                    )
                )
            return

        if parsed.path == "/save-notes":
            fields = parse_qs(body.decode("utf-8", errors="replace"))
            PROJECT_MD_PATH.write_text(fields.get("project_md", [""])[0], encoding="utf-8")
            SCHEDULE_MD_PATH.write_text(fields.get("schedule_md", [""])[0], encoding="utf-8")
            TODO_MD_PATH.write_text(fields.get("todo_md", [""])[0], encoding="utf-8")
            self.send_html(render_dashboard(message="Project notes saved."))
            return

        if parsed.path in {
            "/card-create",
            "/card-update",
            "/card-move",
            "/card-delete",
            "/card-comment",
            "/card-complete-worker",
            "/card-admin-complete-worker",
        }:
            fields = parse_qs(body.decode("utf-8", errors="replace"))
            try:
                if parsed.path == "/card-create":
                    create_card(fields)
                    self.send_html(render_dashboard(message="Card created."))
                elif parsed.path == "/card-update":
                    update_card(fields)
                    self.send_html(render_dashboard(message="Card updated."))
                elif parsed.path == "/card-move":
                    move_card(fields)
                    self.send_html(render_dashboard(message="Card moved."))
                elif parsed.path == "/card-delete":
                    delete_card(fields)
                    self.send_html(render_dashboard(message="Card deleted."))
                elif parsed.path == "/card-comment":
                    add_card_comment(fields)
                    self.send_html(render_dashboard(message="Comment added."))
                elif parsed.path == "/card-complete-worker":
                    complete_card_worker(fields, source="worker")
                    self.send_html(render_dashboard(message="Worker completion confirmation saved."))
                else:
                    complete_card_worker(fields, source="admin")
                    self.send_html(render_dashboard(message="Admin completion confirmation saved."))
            except (ValueError, sqlite3.Error) as exc:
                self.send_html(render_dashboard(error=str(exc)))
            return

        if parsed.path == "/upload":
            content_type = self.headers.get("Content-Type", "")
            fields, file_info = parse_multipart(body, content_type)
            if not file_info or not file_info.get("content"):
                self.send_html(render_dashboard(error="No upload file was received."))
                return
            store_upload(file_info["filename"], file_info["content"], fields.get("author", ""))
            self.send_html(render_dashboard(message="File uploaded and extracted."))
            return

        self.send_error(404)

    def is_authenticated(self) -> bool:
        cookie_header = self.headers.get("Cookie", "")
        jar = cookies.SimpleCookie(cookie_header)
        token = jar.get("project_agent_session")
        return verify_session(token.value if token else None)

    def redirect(self, location: str, session: str | None = None, clear_session: bool = False) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        if session:
            self.send_header(
                "Set-Cookie",
                f"project_agent_session={session}; HttpOnly; SameSite=Lax; Path=/; Max-Age={SESSION_TTL_SECONDS}",
            )
        if clear_session:
            self.send_header("Set-Cookie", "project_agent_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0")
        self.end_headers()

    def send_html(self, content: str, status: int = 200) -> None:
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_static(self, name: str, content_type: str) -> None:
        path = STATIC_DIR / name
        if not path.exists():
            self.send_error(404)
            return
        encoded = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{datetime.now().isoformat(timespec='seconds')}] {self.address_string()} {format % args}")


def render_page(body: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{APP_TITLE}</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
{body}
</body>
</html>"""


def render_gate(error: str = "") -> str:
    setup_mode = not has_password()
    form = ""
    if setup_mode:
        form = """
        <form method="post" action="/setup" class="access-form">
          <label>Access Password</label>
          <input type="password" name="password" minlength="8" required autofocus>
          <button type="submit">Set Password</button>
        </form>
        """
    else:
        form = """
        <form method="post" action="/login" class="access-form">
          <label>Access Password</label>
          <input type="password" name="password" required autofocus>
          <button type="submit">Login</button>
        </form>
        """
    error_html = f'<p class="notice error">{escape(error)}</p>' if error else ""
    return render_page(
        f"""
        <main class="gate">
          <h1>{APP_TITLE}</h1>
          {error_html}
          {form}
        </main>
        """
    )


def render_dashboard(
    query: str = "",
    message: str = "",
    error: str = "",
    llm_question: str = "",
    llm_answer: str = "",
) -> str:
    project_md = read_markdown(PROJECT_MD_PATH)
    schedule_md = read_markdown(SCHEDULE_MD_PATH)
    todo_md = read_markdown(TODO_MD_PATH)
    todo_summary = summarize_todos(todo_md)
    results = search_files(query)
    tree = directory_tree(DATA_DIR)
    total_files = total_file_count()
    llm = llm_config()
    current_llm_status = llm_status()
    cards = list_cards()
    card_counts = card_count_by_status()
    file_options = uploaded_file_options()

    rows = "\n".join(render_file_row(row) for row in results) or """
      <tr><td colspan="5" class="muted">No files found.</td></tr>
    """
    message_html = f'<p class="notice success">{escape(message)}</p>' if message else ""
    error_html = f'<p class="notice error">{escape(error)}</p>' if error else ""
    llm_status_class = "success" if current_llm_status["ok"] else "error"
    llm_status_html = (
        f'<p class="notice {llm_status_class}">'
        f'{escape(current_llm_status["message"])} '
        f'Model: {escape(current_llm_status["model"])} '
        f'Ollama: {escape("reachable" if current_llm_status["ollama_reachable"] else "unreachable")}'
        "</p>"
    )
    llm_answer_html = (
        f'<div class="llm-answer">{escape(llm_answer)}</div>' if llm_answer else '<div class="llm-answer muted">No answer yet.</div>'
    )

    return render_page(
        f"""
        <header class="topbar">
          <div>
            <h1>{APP_TITLE}</h1>
            <p>Project workspace, upload index, schedule, and extracted knowledge base.</p>
          </div>
          <a class="logout" href="/logout">Logout</a>
        </header>

        <main class="dashboard">
          {message_html}
          {error_html}

          <section class="metrics">
            <article>
              <span>Uploaded Files</span>
              <strong>{total_files}</strong>
            </article>
            <article>
              <span>Open Todos</span>
              <strong>{todo_summary['open']}</strong>
            </article>
            <article>
              <span>Done Todos</span>
              <strong>{todo_summary['done']}</strong>
            </article>
            <article>
              <span>Cards</span>
              <strong>{sum(card_counts.values())}</strong>
            </article>
          </section>

          <section class="layout">
            <div class="main-column">
              <section class="panel">
                <div class="panel-head">
                  <h2>Project Management</h2>
                </div>
                <form method="post" action="/save-notes" class="notes-grid">
                  <label>Project Info
                    <textarea name="project_md">{escape(project_md)}</textarea>
                  </label>
                  <label>Schedule
                    <textarea name="schedule_md">{escape(schedule_md)}</textarea>
                  </label>
                  <label>Todos
                    <textarea name="todo_md">{escape(todo_md)}</textarea>
                  </label>
                  <button type="submit">Save Notes</button>
                </form>
              </section>

              <section class="panel">
                <div class="panel-head">
                  <h2>Upload</h2>
                </div>
                <form method="post" action="/upload" enctype="multipart/form-data" class="upload-form">
                  <input type="file" name="file" required>
                  <input type="text" name="author" placeholder="Author">
                  <button type="submit">Upload and Extract</button>
                </form>
              </section>

              <section class="panel">
                <div class="panel-head">
                  <h2>Kanban Cards</h2>
                </div>
                <form method="post" action="/card-create" class="card-create-form">
                  <input type="text" name="card_title" placeholder="Card title" required>
                  <select name="list_name">
                    {render_list_options("todo")}
                  </select>
                  <input type="text" name="assignee" placeholder="Workers, comma separated">
                  <input type="text" name="labels" placeholder="Labels, comma separated">
                  <input type="date" name="due_date">
                  <select name="attachment_file_id">
                    {render_file_options(file_options)}
                  </select>
                  <textarea name="card_description" placeholder="Markdown description"></textarea>
                  <button type="submit">Create Card</button>
                </form>
                <div class="kanban-board">
                  {render_kanban_board(cards, file_options)}
                </div>
              </section>

              <section class="panel">
                <div class="panel-head">
                  <h2>Gemma4 Assistant</h2>
                </div>
                {llm_status_html}
                <form method="post" action="/ask" class="ask-form">
                  <textarea name="question" placeholder="예: 업로드한 파일 중 일정과 관련된 문서는 어디에 있나요?">{escape(llm_question)}</textarea>
                  <button type="submit">Ask Gemma4</button>
                </form>
                {llm_answer_html}
              </section>

              <section class="panel">
                <div class="panel-head">
                  <h2>Search Files</h2>
                  <form method="get" action="/" class="search-form">
                    <input type="search" name="q" value="{escape(query)}" placeholder="filename author content">
                    <button type="submit">Search</button>
                  </form>
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>File</th>
                      <th>Author</th>
                      <th>Size</th>
                      <th>Uploaded</th>
                      <th>Extract MD</th>
                    </tr>
                  </thead>
                  <tbody>{rows}</tbody>
                </table>
              </section>
            </div>

            <aside class="side-column">
              <section class="panel">
                <h2>Storage Tree</h2>
                <pre class="tree">{escape(tree)}</pre>
              </section>

              <section class="panel">
                <h2>Password</h2>
                <form method="post" action="/password" class="password-form">
                  <input type="password" name="current_password" placeholder="Current password" required>
                  <input type="password" name="new_password" placeholder="New password" minlength="8" required>
                  <button type="submit">Change Password</button>
                </form>
              </section>

              <section class="panel">
                <h2>Gemma4 Settings</h2>
                <form method="post" action="/llm-config" class="password-form">
                  <input type="url" name="llm_base_url" value="{escape(llm['base_url'])}" placeholder="http://127.0.0.1:8082">
                  <input type="text" name="llm_generate_path" value="{escape(llm['generate_path'])}" placeholder="/api/generate">
                  <input type="text" name="llm_model" value="{escape(llm['model'])}" placeholder="gemma4:31b">
                  <input type="text" name="llm_user_id" value="{escape(llm['user_id'])}" placeholder="Gemma4 user ID">
                  <input type="password" name="llm_password" placeholder="Gemma4 password">
                  <button type="submit">Save Gemma4</button>
                </form>
              </section>
            </aside>
          </section>
        </main>
        """
    )


def render_file_row(row: sqlite3.Row) -> str:
    md_name = Path(row["md_path"]).name if row["md_path"] else ""
    return f"""
    <tr>
      <td>{escape(row["file_name"])}</td>
      <td>{escape(row["author"] or "")}</td>
      <td>{row["file_size"] or 0}</td>
      <td>{escape(row["uploaded_at"] or "")}</td>
      <td>{escape(md_name)}</td>
    </tr>
    """


def render_kanban_board(cards: dict[str, list[sqlite3.Row]], file_options: list[sqlite3.Row]) -> str:
    columns = []
    for list_name in CARD_LISTS:
        rendered_cards = "\n".join(render_card(card, file_options) for card in cards.get(list_name, []))
        if not rendered_cards:
            rendered_cards = '<p class="muted empty-column">No cards.</p>'
        columns.append(
            f"""
            <section class="kanban-column">
              <h3>{CARD_LIST_LABELS[list_name]} <span>{len(cards.get(list_name, []))}</span></h3>
              {rendered_cards}
            </section>
            """
        )
    return "\n".join(columns)


def render_card(card: sqlite3.Row, file_options: list[sqlite3.Row]) -> str:
    completion = completion_summary_for_card(card)
    labels = [
        f'<span class="card-label">{escape(label.strip())}</span>'
        for label in str(card["labels"] or "").split(",")
        if label.strip()
    ]
    comments = recent_card_comments(int(card["id"]))
    comments_html = "\n".join(
        f'<li><strong>{escape(comment["author"] or "anon")}</strong>: {escape(comment["comment"])}</li>'
        for comment in comments
    )
    attachment_html = ""
    if card["attachment_name"]:
        attachment_html = (
            f'<p class="card-attachment">Attachment: '
            f'<span title="{escape(card["attachment_path"] or "")}">{escape(card["attachment_name"])}</span></p>'
        )
    completion_html = render_card_completion_panel(card, completion)
    return f"""
    <article class="kanban-card">
      <form method="post" action="/card-update" class="card-edit-form">
        <input type="hidden" name="card_id" value="{card['id']}">
        <input type="text" name="card_title" value="{escape(card['title'])}" required>
        <textarea name="card_description">{escape(card['description'] or '')}</textarea>
        <div class="card-fields">
          <select name="list_name">{render_list_options(card['list_name'])}</select>
          <input type="text" name="assignee" value="{escape(card['assignee'] or '')}" placeholder="Workers, comma separated">
          <input type="text" name="labels" value="{escape(card['labels'] or '')}" placeholder="Labels">
          <input type="date" name="due_date" value="{escape(card['due_date'] or '')}">
          <select name="attachment_file_id">{render_file_options(file_options, card['attachment_file_id'])}</select>
        </div>
        <div class="card-meta">
          {''.join(labels)}
          <span>{escape(card['assignee'] or 'no workers')}</span>
          <span>{escape(card['due_date'] or 'no due date')}</span>
        </div>
        {attachment_html}
        <div class="card-actions">
          <button type="submit">Save</button>
        </div>
      </form>
      {completion_html}
      <form method="post" action="/card-move" class="card-move-form">
        <input type="hidden" name="card_id" value="{card['id']}">
        <button name="list_name" value="todo" type="submit">Todo</button>
        <button name="list_name" value="doing" type="submit">Doing</button>
        <button name="list_name" value="done" type="submit">Done</button>
      </form>
      <form method="post" action="/card-comment" class="card-comment-form">
        <input type="hidden" name="card_id" value="{card['id']}">
        <input type="text" name="comment_author" placeholder="Author">
        <input type="text" name="comment" placeholder="Comment" required>
        <button type="submit">Add</button>
      </form>
      <ul class="card-comments">{comments_html}</ul>
      <form method="post" action="/card-delete" class="card-delete-form">
        <input type="hidden" name="card_id" value="{card['id']}">
        <button type="submit">Delete</button>
      </form>
    </article>
    """


def render_card_completion_panel(card: sqlite3.Row, completion: dict[str, Any]) -> str:
    workers = completion["workers"]
    total = completion["total"]
    completed_count = completion["completed_count"]
    completed_by_worker = completion["completed_by_worker"]
    if not workers:
        return '<div class="completion-panel muted">Add worker names to enable completion confirmation.</div>'

    worker_items = []
    for worker in workers:
        row = completed_by_worker.get(worker.lower())
        if row:
            source = "admin" if row["source"] == "admin" else "worker"
            note = f' title="{escape(row["note"] or "")}"' if row["note"] else ""
            worker_items.append(
                f'<span class="worker-chip done"{note}>{escape(worker)} done by {escape(row["confirmed_by"] or source)}</span>'
            )
        else:
            worker_items.append(f'<span class="worker-chip">{escape(worker)} pending</span>')

    worker_options = "\n".join(f'<option value="{escape(worker)}">{escape(worker)}</option>' for worker in workers)
    return f"""
    <div class="completion-panel">
      <div class="completion-head">
        <span>Completion {completed_count}/{total}</span>
        <progress value="{completed_count}" max="{total}"></progress>
      </div>
      <div class="worker-list">{''.join(worker_items)}</div>
      <form method="post" action="/card-complete-worker" class="completion-form">
        <input type="hidden" name="card_id" value="{card['id']}">
        <select name="worker_name">{worker_options}</select>
        <input type="text" name="confirmed_by" placeholder="Worker name">
        <input type="text" name="completion_note" placeholder="Completion note">
        <button type="submit">Worker Done</button>
      </form>
      <form method="post" action="/card-admin-complete-worker" class="completion-form">
        <input type="hidden" name="card_id" value="{card['id']}">
        <select name="worker_name">{worker_options}</select>
        <input type="text" name="confirmed_by" value="admin" placeholder="Manager">
        <input type="text" name="completion_note" placeholder="Manager note">
        <button type="submit">Admin Confirm</button>
      </form>
    </div>
    """


def render_list_options(selected: str) -> str:
    selected = normalize_card_list(str(selected))
    return "\n".join(
        f'<option value="{name}"{" selected" if name == selected else ""}>{label}</option>'
        for name, label in CARD_LIST_LABELS.items()
    )


def render_file_options(files: list[sqlite3.Row], selected_id: int | None = None) -> str:
    options = ['<option value="">No attachment</option>']
    for file_row in files:
        selected = " selected" if selected_id and int(file_row["id"]) == int(selected_id) else ""
        options.append(f'<option value="{file_row["id"]}"{selected}>{escape(file_row["file_name"])}</option>')
    return "\n".join(options)


def total_file_count() -> int:
    with sqlite3.connect(DB_PATH) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM files").fetchone()[0])


def llm_config() -> dict[str, str]:
    config = load_config()
    llm = config.get("llm") or {}
    return {
        "base_url": str(llm.get("base_url") or DEFAULT_LLM_BASE_URL).rstrip("/"),
        "generate_path": str(llm.get("generate_path") or DEFAULT_LLM_GENERATE_PATH),
        "model": str(llm.get("model") or DEFAULT_LLM_MODEL),
        "user_id": str(llm.get("user_id") or ""),
        "password": str(llm.get("password") or ""),
    }


def save_llm_config(fields: dict[str, list[str]]) -> None:
    config = load_config()
    current = llm_config()
    password = fields.get("llm_password", [""])[0]
    config["llm"] = {
        "base_url": fields.get("llm_base_url", [current["base_url"]])[0].strip().rstrip("/"),
        "generate_path": fields.get("llm_generate_path", [current["generate_path"]])[0].strip() or "/api/generate",
        "model": fields.get("llm_model", [current["model"]])[0].strip() or DEFAULT_LLM_MODEL,
        "user_id": fields.get("llm_user_id", [current["user_id"]])[0].strip(),
        "password": password if password else current["password"],
    }
    save_config(config)


def llm_status() -> dict[str, Any]:
    config = llm_config()
    status_url = config["base_url"] + "/api/status"
    try:
        with urllib.request.urlopen(status_url, timeout=2) as response:
            data = json.loads(response.read().decode("utf-8"))
        return {
            "ok": True,
            "message": "Gemma4 server reachable.",
            "model": str(data.get("model") or config["model"]),
            "ollama_reachable": bool(data.get("ollama_reachable")),
        }
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "message": f"Gemma4 server unavailable: {exc}",
            "model": config["model"],
            "ollama_reachable": False,
        }


def call_gemma4(prompt: str) -> dict[str, Any]:
    config = llm_config()
    if not config["base_url"]:
        return {"ok": False, "answer": "", "error": "LLM server URL is not configured."}
    if not config["user_id"] or not config["password"]:
        return {"ok": False, "answer": "", "error": "LLM user ID/password is not configured."}

    url = config["base_url"] + config["generate_path"]
    payload = {
        "user_id": config["user_id"],
        "password": config["password"],
        "prompt": prompt,
        "model": config["model"],
        "keep_alive": "30m",
        "options": {"num_ctx": 8192},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        started = time.perf_counter()
        with urllib.request.urlopen(request, timeout=DEFAULT_LLM_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
        return {
            "ok": True,
            "answer": str(data.get("response") or ""),
            "error": str(data.get("error") or ""),
            "model": str(data.get("model") or config["model"]),
            "elapsed_seconds": float(data.get("elapsed_seconds") or (time.perf_counter() - started)),
        }
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"ok": False, "answer": "", "error": str(exc), "model": config["model"]}


def build_project_context(question: str) -> str:
    matched_files = search_files(question)[:8] if question.strip() else search_files("")[:8]
    file_lines = []
    for row in matched_files:
        content = str(row["content"] or "").replace("\r", " ").replace("\n", " ")
        file_lines.append(
            "- "
            f"file_name={row['file_name']}; author={row['author'] or 'unknown'}; "
            f"stored_path={row['stored_path']}; md_path={row['md_path']}; "
            f"content_preview={content[:900]}"
        )
    if not file_lines:
        file_lines.append("- no uploaded file records found")

    card_lines = []
    for list_name, rows in list_cards().items():
        for card in rows[:12]:
            completion = completion_summary_for_card(card)
            completed_workers = [
                worker
                for worker in completion["workers"]
                if worker.lower() in completion["completed_by_worker"]
            ]
            pending_workers = [
                worker
                for worker in completion["workers"]
                if worker.lower() not in completion["completed_by_worker"]
            ]
            card_lines.append(
                "- "
                f"status={CARD_LIST_LABELS.get(list_name, list_name)}; "
                f"title={card['title']}; assignee={card['assignee'] or 'unassigned'}; "
                f"completed_workers={', '.join(completed_workers) or 'none'}; "
                f"pending_workers={', '.join(pending_workers) or 'none'}; "
                f"labels={card['labels'] or ''}; due_date={card['due_date'] or ''}; "
                f"attachment={card['attachment_path'] or ''}; description={(card['description'] or '')[:500]}"
            )
    if not card_lines:
        card_lines.append("- no kanban cards found")

    return "\n".join(
        [
            "You are Project Agent, a local project assistant.",
            "Answer in Korean unless the user asks otherwise.",
            "Use the provided local project data. If a file location is relevant, include its stored_path or md_path.",
            "",
            "Project info markdown:",
            read_markdown(PROJECT_MD_PATH)[:2500],
            "",
            "Schedule markdown:",
            read_markdown(SCHEDULE_MD_PATH)[:2500],
            "",
            "Todo markdown:",
            read_markdown(TODO_MD_PATH)[:2500],
            "",
            "Storage root:",
            str(DATA_DIR),
            "",
            "Current storage tree:",
            directory_tree(DATA_DIR, max_depth=3, max_items=120),
            "",
            "Matched uploaded files:",
            "\n".join(file_lines),
            "",
            "Kanban cards:",
            "\n".join(card_lines),
            "",
            "User question:",
            question,
        ]
    )


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def main() -> None:
    ensure_storage()
    host = os.environ.get("PROJECT_AGENT_HOST", "127.0.0.1")
    port = int(os.environ.get("PROJECT_AGENT_PORT", "18765"))
    server = ThreadingHTTPServer((host, port), ProjectAgentHandler)
    print(f"{APP_TITLE} running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
