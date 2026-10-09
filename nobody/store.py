"""SQLite storage for transcripts and summaries."""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TranscriptRow:
    """A single transcript segment."""

    id: int
    session_id: str
    source: str
    start_ms: int
    end_ms: int
    text: str


@dataclass
class SummaryRow:
    """A session summary."""

    session_id: str
    summary_json: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.summary_json)


class TranscriptStore:
    """SQLite storage for transcript segments."""

    def __init__(self, db_path: str | Path = "transcripts.db") -> None:
        self.db_path = Path(db_path)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                source TEXT NOT NULL,
                start_ms INTEGER NOT NULL,
                end_ms INTEGER NOT NULL,
                text TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_transcripts_session
            ON transcripts(session_id, start_ms)
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                session_id TEXT PRIMARY KEY,
                summary_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        self._conn.commit()

    def create_session(self) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())
        self._conn.execute("INSERT INTO sessions (id) VALUES (?)", (session_id,))
        self._conn.commit()
        return session_id

    def add_transcript(
        self,
        session_id: str,
        source: str,
        start_ms: int,
        end_ms: int,
        text: str,
    ) -> int:
        """Add a transcript segment and return its row ID."""
        cur = self._conn.execute(
            """
            INSERT INTO transcripts (session_id, source, start_ms, end_ms, text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, source, start_ms, end_ms, text),
        )
        self._conn.commit()
        return cur.lastrowid or 0

    def get_session_transcripts(self, session_id: str) -> list[TranscriptRow]:
        """Get all transcripts for a session, ordered by time."""
        cur = self._conn.execute(
            """
            SELECT id, session_id, source, start_ms, end_ms, text
            FROM transcripts
            WHERE session_id = ?
            ORDER BY start_ms
            """,
            (session_id,),
        )
        return [TranscriptRow(*row) for row in cur.fetchall()]

    def get_merged_transcript(self, session_id: str) -> str:
        """Get a merged transcript with speaker labels."""
        rows = self.get_session_transcripts(session_id)
        lines = []
        for row in rows:
            speaker = "Host" if row.source == "me" else "Guests"
            lines.append(f"[{speaker}] {row.text.strip()}")
        return "\n".join(lines)

    def save_summary(self, session_id: str, summary: dict[str, Any]) -> None:
        """Save or update a summary for a session."""
        summary_json = json.dumps(summary)
        self._conn.execute(
            """
            INSERT OR REPLACE INTO summaries (session_id, summary_json, created_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (session_id, summary_json),
        )
        self._conn.commit()

    def get_summary(self, session_id: str) -> SummaryRow | None:
        """Get the summary for a session, if it exists."""
        cur = self._conn.execute(
            "SELECT session_id, summary_json, created_at FROM summaries WHERE session_id = ?",
            (session_id,),
        )
        row = cur.fetchone()
        if row:
            return SummaryRow(*row)
        return None

    def delete_summary(self, session_id: str) -> bool:
        """Delete a summary. Returns True if one was deleted."""
        cur = self._conn.execute(
            "DELETE FROM summaries WHERE session_id = ?",
            (session_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        self._conn.close()
