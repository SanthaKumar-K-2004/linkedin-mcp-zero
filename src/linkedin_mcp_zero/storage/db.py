from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

from linkedin_mcp_zero.config.defaults import DATA_DIR_NAME
from linkedin_mcp_zero.config.settings import Settings

# Minimum interval between scheduled alert runs, per freq. Unknown freq values
# (e.g. hand-edited rows) deliberately fall back to "daily" rather than
# "always due" so a typo can never turn an alert into a scraper hammer.
ALERT_FREQ_HOURS: dict[str, float] = {"daily": 24.0, "weekly": 168.0}
# Scheduler jitter grace: a cron that runs every hour should still see a daily
# alert as due near the 24h mark instead of missing it by minutes.
ALERT_DUE_GRACE_HOURS = 0.5


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
            # Migrate databases created by older releases that stored no
            # last_run_at column (needed to honor the daily/weekly freq).
            cols = {row[1] for row in conn.execute("PRAGMA table_info(alerts)").fetchall()}
            if "last_run_at" not in cols:
                conn.execute("ALTER TABLE alerts ADD COLUMN last_run_at TEXT")

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
            rows = conn.execute("SELECT id, name, kw, loc, freq, last_run_at FROM alerts ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def alert_due(self, alert: dict[str, Any], now: datetime | None = None) -> tuple[bool, float]:
        """Decide whether an alert should run now per its freq.

        Returns ``(due, hours_until_due)``. Alerts never run (or with an
        unparseable timestamp) are always due; a failed parse must not make
        an alert go permanently silent.
        """
        last_run_raw = str(alert.get("last_run_at") or "").strip()
        if not last_run_raw:
            return True, 0.0
        try:
            last_run = datetime.fromisoformat(last_run_raw)
            if last_run.tzinfo is None:
                last_run = last_run.replace(tzinfo=timezone.utc)
        except ValueError:
            return True, 0.0
        interval = ALERT_FREQ_HOURS.get(str(alert.get("freq") or "daily").lower(), ALERT_FREQ_HOURS["daily"])
        current = now or datetime.now(timezone.utc)
        elapsed_h = (current - last_run.astimezone(timezone.utc)).total_seconds() / 3600
        remaining = interval - ALERT_DUE_GRACE_HOURS - elapsed_h
        return (remaining <= 0), max(0.0, remaining)

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
        run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "UPDATE alerts SET last_ids = ?, last_run_at = ? WHERE id = ?",
                (json.dumps(job_ids, ensure_ascii=True), run_at, alert_id),
            )
