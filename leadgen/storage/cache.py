import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


# В text лежит сырой ответ сайта (HTML, robots.txt), а не извлечённый текст:
# из HTML берутся ссылки на страницы и mailto-адреса, и повторный прогон
# не ходит в сеть. Пустая строка — страница не загрузилась.
class PageCache:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS pages (url TEXT PRIMARY KEY, text TEXT NOT NULL, fetched_at TEXT NOT NULL)"
            )

    # Своё соединение на каждую операцию: ветки графа работают в разных потоках,
    # а соединение sqlite3 нельзя передавать между потоками.
    def _connect(self):
        return closing(sqlite3.connect(self.db_path))

    def get(self, url: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT text FROM pages WHERE url = ?", (url,)).fetchone()
        return row[0] if row else None

    def put(self, url: str, text: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO pages (url, text, fetched_at) VALUES (?, ?, ?)",
                (url, text, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
