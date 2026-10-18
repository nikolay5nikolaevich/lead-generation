import hashlib
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


# Ключ — хэш всего, что уходит в модель (промпт + схема ответа). Поменялся промпт хоть
# на символ — новый ключ и новый вызов. Кладём только ответы, прошедшие проверку схемой.
class LlmCache:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS llm_cache (key TEXT PRIMARY KEY, response TEXT NOT NULL, created_at TEXT NOT NULL)"
            )

    # Своё соединение на каждую операцию — как в PageCache: ветки графа в разных потоках.
    def _connect(self):
        return closing(sqlite3.connect(self.db_path))

    @staticmethod
    def key(prompt: str, schema: str) -> str:
        return hashlib.sha256(f"{prompt}\n{schema}".encode("utf-8")).hexdigest()

    def get(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT response FROM llm_cache WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def put(self, key: str, response: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO llm_cache (key, response, created_at) VALUES (?, ?, ?)",
                (key, response, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
