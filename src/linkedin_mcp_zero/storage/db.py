from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

from linkedin_mcp_zero.config.defaults import DATA_DIR_NAME
from linkedin_mcp_zero.config.settings import Settings


class Storage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        base = Path(settings.data_dir or user_data_dir(DATA_DIR_NAME))
        base.mkdir(parents=True, exist_ok=True)
        self.base_dir = base
        self.db_path = base / "state.sqlite3"
        self.exports_dir = base / "exports"
        self.exports_dir.mkdir(exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS resumes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    kw TEXT NOT NULL,
                    loc TEXT DEFAULT '',
                    freq TEXT DEFAULT 'daily',
                    last_ids TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def save_resume(self, path: str, data: dict[str, Any]) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO resumes(path, data) VALUES (?, ?)",
                (path, json.dumps(data, ensure_ascii=True)),
            )
            return cur.lastrowid if cur.lastrowid is not None else 0

    def get_resume(self, resume_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT data FROM resumes WHERE id = ?", (resume_id,)).fetchone()
        return json.loads(row["data"]) if row else None

    def save_alert(self, name: str, kw: str, loc: str = "", freq: str = "daily") -> dict[str, Any]:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO alerts(name, kw, loc, freq) VALUES (?, ?, ?, ?)",
                (name, kw, loc, freq),
            )
            alert_id = cur.lastrowid if cur.lastrowid is not None else 0
        return {
            "id": alert_id,
            "name": name,
            "kw": kw,
            "loc": loc,
            "freq": freq,
            "status": "active",
        }

    def list_alerts(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, name, kw, loc, freq FROM alerts ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def selected_alerts(self, ids: list[int] | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if ids:
                try:
                    coerced_ids = [int(i) for i in ids]
                except (ValueError, TypeError) as e:
                    raise ValueError(f"Invalid alert IDs: {ids}") from e
                marks = ",".join("?" for _ in coerced_ids)
                rows = conn.execute(
                    f"SELECT * FROM alerts WHERE id IN ({marks}) ORDER BY id",  # nosec B608
                    tuple(coerced_ids),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM alerts ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def update_alert_seen(self, alert_id: int, job_ids: list[str]) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE alerts SET last_ids = ? WHERE id = ?",
                (json.dumps(job_ids, ensure_ascii=True), alert_id),
            )
