"""Local SQLite store for delete stats, warn/kick state, and admin notify prefs."""

from __future__ import annotations

import html
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class StatsStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS deletions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    deleted_at TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_deletions_user
                    ON deletions(guild_id, user_id);
                CREATE TABLE IF NOT EXISTS notify_prefs (
                    user_id INTEGER PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS enforcement (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    warn_sent_at TEXT,
                    kick_armed_at TEXT,
                    kick_expires_at TEXT,
                    PRIMARY KEY (guild_id, user_id)
                );
                """
            )

    def record_deletion(
        self,
        guild_id: int,
        user_id: int,
        channel_id: int,
        reason: str = "",
        deleted_at: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO deletions (guild_id, user_id, channel_id, deleted_at, reason)
                VALUES (?, ?, ?, ?, ?)
                """,
                (guild_id, user_id, channel_id, deleted_at or _utc_now(), reason),
            )

    def deletion_count(self, guild_id: int, user_id: int | None = None) -> int:
        with self._connect() as conn:
            if user_id is None:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM deletions WHERE guild_id = ?",
                    (guild_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS n FROM deletions
                    WHERE guild_id = ? AND user_id = ?
                    """,
                    (guild_id, user_id),
                ).fetchone()
            return int(row["n"]) if row else 0

    def deletions_for_user(
        self, guild_id: int, user_id: int, limit: int = 100
    ) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT channel_id, deleted_at, reason
                    FROM deletions
                    WHERE guild_id = ? AND user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (guild_id, user_id, limit),
                )
            )

    def user_summaries(self, guild_id: int) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT user_id,
                           COUNT(*) AS delete_count,
                           MAX(deleted_at) AS last_deleted_at
                    FROM deletions
                    WHERE guild_id = ?
                    GROUP BY user_id
                    ORDER BY delete_count DESC, last_deleted_at DESC
                    """,
                    (guild_id,),
                )
            )

    def set_notify(self, user_id: int, enabled: bool) -> None:
        with self._connect() as conn:
            if enabled:
                conn.execute(
                    "INSERT OR IGNORE INTO notify_prefs (user_id) VALUES (?)",
                    (user_id,),
                )
            else:
                conn.execute(
                    "DELETE FROM notify_prefs WHERE user_id = ?",
                    (user_id,),
                )

    def notify_enabled(self, user_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM notify_prefs WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return row is not None

    def notify_user_ids(self) -> list[int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT user_id FROM notify_prefs").fetchall()
            return [int(row["user_id"]) for row in rows]

    def get_enforcement(self, guild_id: int, user_id: int) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT warn_sent_at, kick_armed_at, kick_expires_at
                FROM enforcement
                WHERE guild_id = ? AND user_id = ?
                """,
                (guild_id, user_id),
            ).fetchone()

    def set_warn_sent(self, guild_id: int, user_id: int, when: str | None = None) -> None:
        stamp = when or _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO enforcement (guild_id, user_id, warn_sent_at)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    warn_sent_at = excluded.warn_sent_at
                """,
                (guild_id, user_id, stamp),
            )

    def arm_kick_window(
        self,
        guild_id: int,
        user_id: int,
        armed_at: str,
        expires_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO enforcement (
                    guild_id, user_id, kick_armed_at, kick_expires_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id) DO UPDATE SET
                    kick_armed_at = excluded.kick_armed_at,
                    kick_expires_at = excluded.kick_expires_at
                """,
                (guild_id, user_id, armed_at, expires_at),
            )

    def clear_enforcement(self, guild_id: int, user_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM enforcement WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            )

    def kick_window_active(self, guild_id: int, user_id: int) -> bool:
        row = self.get_enforcement(guild_id, user_id)
        if row is None or not row["kick_expires_at"]:
            return False
        try:
            expires = datetime.strptime(
                row["kick_expires_at"], "%Y-%m-%d %H:%M:%S UTC"
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            return False
        return datetime.now(timezone.utc) < expires

    def render_html(
        self,
        guild_id: int,
        guild_name: str,
        user_id: int | None = None,
    ) -> str:
        """Build a self-contained HTML report for admin DMs."""
        generated = _utc_now()
        if user_id is None:
            rows = self.user_summaries(guild_id)
            title = f"ZeeNoodle stats — {html.escape(guild_name)}"
            body_rows = []
            for row in rows:
                body_rows.append(
                    "<tr>"
                    f"<td>{row['user_id']}</td>"
                    f"<td>{row['delete_count']}</td>"
                    f"<td>{html.escape(str(row['last_deleted_at'] or ''))}</td>"
                    "</tr>"
                )
            table = (
                "<table><thead><tr>"
                "<th>User ID</th><th>Deletes</th><th>Last deleted</th>"
                "</tr></thead><tbody>"
                + ("".join(body_rows) or "<tr><td colspan='3'>No deletions yet.</td></tr>")
                + "</tbody></table>"
            )
            summary = f"<p>Total users with deletes: <strong>{len(rows)}</strong></p>"
        else:
            detail = self.deletions_for_user(guild_id, user_id)
            count = self.deletion_count(guild_id, user_id)
            title = f"ZeeNoodle stats — user {user_id}"
            body_rows = []
            for row in detail:
                body_rows.append(
                    "<tr>"
                    f"<td>{row['channel_id']}</td>"
                    f"<td>{html.escape(str(row['deleted_at']))}</td>"
                    f"<td>{html.escape(str(row['reason'] or ''))}</td>"
                    "</tr>"
                )
            table = (
                "<table><thead><tr>"
                "<th>Channel ID</th><th>When</th><th>Why</th>"
                "</tr></thead><tbody>"
                + ("".join(body_rows) or "<tr><td colspan='3'>No deletions for this user.</td></tr>")
                + "</tbody></table>"
            )
            summary = f"<p>Total deletes for this user: <strong>{count}</strong></p>"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
body {{ font-family: Segoe UI, sans-serif; margin: 2rem; background: #0f1115; color: #e8eaed; }}
h1 {{ font-size: 1.4rem; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
th, td {{ border: 1px solid #333; padding: 0.5rem 0.75rem; text-align: left; }}
th {{ background: #1a1d24; }}
tr:nth-child(even) {{ background: #161920; }}
.meta {{ color: #9aa0a6; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="meta">Generated {html.escape(generated)} · private admin report</p>
{summary}
{table}
</body>
</html>
"""
