from __future__ import annotations
import json, sqlite3, threading, time, uuid
from pathlib import Path
from typing import Any

class ExplicitMemoryStore:
    """User-scoped memory that writes only after explicit caller consent."""
    def __init__(self, path: str | Path) -> None:
        self.path, self._lock = Path(path), threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS explicit_memories (
              id TEXT PRIMARY KEY, user_id TEXT NOT NULL, content TEXT NOT NULL,
              metadata_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_memories_user ON explicit_memories(user_id, updated_at DESC)")
    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10); db.row_factory = sqlite3.Row; return db
    def remember(self, user_id: str, content: str, metadata: dict[str, Any] | None = None) -> str:
        user_id, content = user_id.strip(), content.strip()
        if not user_id: raise ValueError("user_id is required to save memory.")
        if not content: raise ValueError("memory content is required.")
        memory_id, now = uuid.uuid4().hex, time.time()
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO explicit_memories VALUES (?, ?, ?, ?, ?, ?)", (memory_id, user_id, content, json.dumps(metadata or {}, ensure_ascii=False), now, now))
        return memory_id
    def list_for_user(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        if not user_id.strip() or limit <= 0: return []
        with self._lock, self._connect() as db:
            rows = db.execute("SELECT * FROM explicit_memories WHERE user_id=? ORDER BY updated_at DESC LIMIT ?", (user_id.strip(), limit)).fetchall()
        return [{"id": r["id"], "content": r["content"], "metadata": json.loads(r["metadata_json"] or "{}"), "created_at": r["created_at"], "updated_at": r["updated_at"]} for r in rows]
    def delete(self, user_id: str, memory_id: str) -> bool:
        with self._lock, self._connect() as db: return db.execute("DELETE FROM explicit_memories WHERE id=? AND user_id=?", (memory_id, user_id.strip())).rowcount > 0
    def clear_user(self, user_id: str) -> int:
        with self._lock, self._connect() as db: return db.execute("DELETE FROM explicit_memories WHERE user_id=?", (user_id.strip(),)).rowcount
