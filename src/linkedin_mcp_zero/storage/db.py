from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import suppress
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
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        if self.db_path.exists():
            with suppress(Exception):
                os.chmod(self.db_path, 0o600)
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
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
                    job_id UNINDEXED,
                    title,
                    company,
                    location,
                    description,
                    skills,
                    tokenize = 'porter unicode61'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS skill_graph (
                    source_skill TEXT NOT NULL,
                    target_skill TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    PRIMARY KEY (source_skill, target_skill)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_metadata (
                    job_id TEXT PRIMARY KEY,
                    first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    repost_count INTEGER DEFAULT 0,
                    applicants_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                )
                """
            )
        if self.db_path.exists():
            with suppress(Exception):
                os.chmod(self.db_path, 0o600)

    def record_skill_cooccurrences(self, skills: list[str]) -> None:
        """Dynamically learn real-time skill relationships from actual scraped jobs and real resumes."""
        cleaned = list({s.strip().lower() for s in skills if isinstance(s, str) and len(s.strip()) > 1})
        if len(cleaned) < 2:
            return
        with self._connect() as conn:
            for i, s1 in enumerate(cleaned):
                for s2 in cleaned[i + 1 :]:
                    if s1 != s2:
                        conn.execute(
                            """
                            INSERT INTO skill_graph(source_skill, target_skill, relation, weight)
                            VALUES (?, ?, 'co_occurs_with', 1.0)
                            ON CONFLICT(source_skill, target_skill) DO UPDATE SET
                                weight = weight + 1.0
                            """,
                            (s1, s2),
                        )
                        conn.execute(
                            """
                            INSERT INTO skill_graph(source_skill, target_skill, relation, weight)
                            VALUES (?, ?, 'co_occurs_with', 1.0)
                            ON CONFLICT(source_skill, target_skill) DO UPDATE SET
                                weight = weight + 1.0
                            """,
                            (s2, s1),
                        )

    def save_resume(self, path: str, data: dict[str, Any]) -> int:
        skills = data.get("skills", [])
        if isinstance(skills, list) and skills:
            self.record_skill_cooccurrences(skills)
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

    def index_job_fts(
        self,
        job_id: str,
        title: str,
        company: str,
        location: str,
        description: str,
        skills: str = "",
    ) -> None:
        if skills:
            parsed_skills = [s.strip() for s in skills.split() if s.strip()]
            if len(parsed_skills) >= 2:
                self.record_skill_cooccurrences(parsed_skills)
        with self._connect() as conn:
            conn.execute("DELETE FROM jobs_fts WHERE job_id = ?", (job_id,))
            conn.execute(
                "INSERT INTO jobs_fts(job_id, title, company, location, description, skills) VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, title, company, location, description, skills),
            )

    def search_jobs_fts(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        clean_tokens = [re.sub(r"[^\w]", "", token) for token in query.split()]
        clean_query = " OR ".join(f'"{t}"*' for t in clean_tokens if t)
        if not clean_query:
            return []
        with self._connect() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT job_id, title, company, location, description, bm25(jobs_fts) as rank
                    FROM jobs_fts
                    WHERE jobs_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (clean_query, limit),
                ).fetchall()
                return [dict(row) for row in rows]
            except Exception:
                return []

    def expand_skills(self, skills: list[str]) -> dict[str, list[str]]:
        """Expand candidate skills into related concepts and technologies via skill graph."""
        res: dict[str, list[str]] = {}
        with self._connect() as conn:
            for skill in skills:
                if not skill or not isinstance(skill, str):
                    continue
                normalized = skill.lower().strip()
                rows = conn.execute(
                    "SELECT target_skill FROM skill_graph WHERE source_skill = ?",
                    (normalized,),
                ).fetchall()
                if rows:
                    res[skill] = [row["target_skill"] for row in rows]
                else:
                    rev_rows = conn.execute(
                        "SELECT source_skill FROM skill_graph WHERE target_skill = ?",
                        (normalized,),
                    ).fetchall()
                    if rev_rows:
                        res[skill] = [row["source_skill"] for row in rev_rows]
        return res

    def get_skill_cluster(self, skill: str) -> dict[str, Any]:
        """Return the cluster of related technologies and capabilities for a skill."""
        if not skill or not isinstance(skill, str):
            return {"skill": str(skill or ""), "direct_connections": [], "related_from": [], "total_connections": 0}
        normalized = skill.lower().strip()
        with self._connect() as conn:
            direct = conn.execute(
                "SELECT target_skill, relation, weight FROM skill_graph WHERE source_skill = ?",
                (normalized,),
            ).fetchall()
            reverse = conn.execute(
                "SELECT source_skill, relation, weight FROM skill_graph WHERE target_skill = ?",
                (normalized,),
            ).fetchall()
        return {
            "skill": skill,
            "direct_connections": [dict(r) for r in direct],
            "related_from": [dict(r) for r in reverse],
            "total_connections": len(direct) + len(reverse),
        }

    def record_job_metadata(
        self,
        job_id: str,
        applicants_count: int = 0,
        repost_count: int = 0,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO job_metadata(job_id, applicants_count, repost_count, last_seen_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(job_id) DO UPDATE SET
                    applicants_count = excluded.applicants_count,
                    repost_count = excluded.repost_count,
                    last_seen_at = CURRENT_TIMESTAMP
                """,
                (job_id, applicants_count, repost_count),
            )

    def get_job_metadata(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM job_metadata WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        return dict(row) if row else None
