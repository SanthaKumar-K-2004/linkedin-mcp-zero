from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

from linkedin_mcp_zero.config.defaults import DATA_DIR_NAME
from linkedin_mcp_zero.config.settings import Settings


class MetricsStore:
    def __init__(self, settings: Settings) -> None:
        base = Path(settings.data_dir or user_data_dir(DATA_DIR_NAME)).expanduser()
        base.mkdir(parents=True, exist_ok=True)
        self.db_path = base / "metrics.sqlite3"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tool_name TEXT NOT NULL,
                    engine TEXT NOT NULL,
                    called_at TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    success INTEGER NOT NULL,
                    error_type TEXT,
                    response_chars INTEGER NOT NULL,
                    response_bytes INTEGER NOT NULL,
                    tokens_estimated INTEGER NOT NULL,
                    tokens_exact INTEGER,
                    tokens_source TEXT NOT NULL DEFAULT 'estimate'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS browser_caps (
                    action_type TEXT PRIMARY KEY,
                    day TEXT NOT NULL,
                    calls INTEGER NOT NULL DEFAULT 0
                )
                """
            )

    def insert_call(
        self,
        *,
        tool_name: str,
        engine: str,
        called_at: str,
        duration_ms: int,
        success: bool,
        error_type: str | None,
        response_chars: int,
        response_bytes: int,
        tokens_estimated: int,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO tool_calls(
                    tool_name, engine, called_at, duration_ms, success, error_type,
                    response_chars, response_bytes, tokens_estimated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tool_name,
                    engine,
                    called_at,
                    duration_ms,
                    1 if success else 0,
                    error_type,
                    response_chars,
                    response_bytes,
                    tokens_estimated,
                ),
            )
            return int(cur.lastrowid)

    def update_exact_tokens(self, row_id: int, tokens: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tool_calls
                SET tokens_exact = ?, tokens_source = 'anthropic_count_tokens'
                WHERE id = ?
                """,
                (tokens, row_id),
            )

    def recent_calls(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, tool_name, engine, called_at, duration_ms, success, error_type,
                       response_chars, response_bytes, tokens_estimated, tokens_exact, tokens_source
                FROM tool_calls
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def summary(self) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT tool_name, engine, COUNT(*) AS calls,
                       SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS errors,
                       ROUND(AVG(duration_ms), 1) AS avg_duration_ms,
                       SUM(tokens_estimated) AS estimated_tokens,
                       SUM(COALESCE(tokens_exact, 0)) AS exact_tokens_known
                FROM tool_calls
                GROUP BY tool_name, engine
                ORDER BY calls DESC, tool_name
                """
            ).fetchall()
        return {"tools": [dict(row) for row in rows]}

    def reset(self) -> int:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM tool_calls")
            return int(cur.rowcount)

    def browser_cap(self, action_type: str, day: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT calls FROM browser_caps WHERE action_type = ? AND day = ?",
                (action_type, day),
            ).fetchone()
        return int(row["calls"]) if row else 0

    def increment_browser_cap(self, action_type: str, day: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO browser_caps(action_type, day, calls) VALUES (?, ?, 1)
                ON CONFLICT(action_type) DO UPDATE SET
                    day = excluded.day,
                    calls = CASE
                        WHEN browser_caps.day = excluded.day THEN browser_caps.calls + 1
                        ELSE 1
                    END
                """,
                (action_type, day),
            )
