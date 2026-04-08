"""SQLite + FTS5 database layer for MindGraph fingerprint index."""
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_DIR = ".mindgraph"
DB_NAME = "mindgraph.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file TEXT NOT NULL,
    heading TEXT NOT NULL,
    heading_level INTEGER NOT NULL,
    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    brief TEXT,
    fingerprint TEXT,
    content_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_sections_file_heading_line
    ON sections(file, heading, line_start);

CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts USING fts5(
    brief, fingerprint, content=sections, content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS sections_ai AFTER INSERT ON sections BEGIN
    INSERT INTO sections_fts(rowid, brief, fingerprint)
    VALUES (new.id, new.brief, new.fingerprint);
END;

CREATE TRIGGER IF NOT EXISTS sections_ad AFTER DELETE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, brief, fingerprint)
    VALUES('delete', old.id, old.brief, old.fingerprint);
END;

CREATE TRIGGER IF NOT EXISTS sections_au AFTER UPDATE ON sections BEGIN
    INSERT INTO sections_fts(sections_fts, rowid, brief, fingerprint)
    VALUES('delete', old.id, old.brief, old.fingerprint);
    INSERT INTO sections_fts(rowid, brief, fingerprint)
    VALUES (new.id, new.brief, new.fingerprint);
END;

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def get_db_path(kb_root: Path) -> Path:
    return kb_root / DB_DIR / DB_NAME


def get_connection(kb_root: Path) -> sqlite3.Connection:
    db_path = get_db_path(kb_root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def upsert_section(
    conn: sqlite3.Connection,
    file: str,
    heading: str,
    heading_level: int,
    line_start: int,
    line_end: int,
    brief: str,
    fingerprint: str,
    content_hash: str,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """INSERT INTO sections (file, heading, heading_level, line_start, line_end,
                                brief, fingerprint, content_hash, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(file, heading, line_start) DO UPDATE SET
               heading_level=excluded.heading_level,
               line_end=excluded.line_end,
               brief=excluded.brief,
               fingerprint=excluded.fingerprint,
               content_hash=excluded.content_hash,
               updated_at=excluded.updated_at""",
        (file, heading, heading_level, line_start, line_end,
         brief, fingerprint, content_hash, now),
    )
    conn.commit()
    return cursor.lastrowid


def delete_sections_for_file(conn: sqlite3.Connection, file: str) -> int:
    cursor = conn.execute("DELETE FROM sections WHERE file = ?", (file,))
    conn.commit()
    return cursor.rowcount


def delete_stale_sections(
    conn: sqlite3.Connection, file: str, valid_hashes: set
) -> int:
    rows = conn.execute(
        "SELECT id, content_hash FROM sections WHERE file = ?", (file,)
    ).fetchall()
    stale_ids = [r["id"] for r in rows if r["content_hash"] not in valid_hashes]
    if stale_ids:
        placeholders = ",".join("?" * len(stale_ids))
        conn.execute(f"DELETE FROM sections WHERE id IN ({placeholders})", stale_ids)
        conn.commit()
    return len(stale_ids)


def search_fts(
    conn: sqlite3.Connection, query: str, limit: int = 20
) -> list[dict]:
    rows = conn.execute(
        """SELECT s.file, s.heading, s.line_start, s.line_end, s.brief,
                  rank
           FROM sections_fts fts
           JOIN sections s ON s.id = fts.rowid
           WHERE sections_fts MATCH ?
           ORDER BY rank
           LIMIT ?""",
        (query, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_sections(conn: sqlite3.Connection, file: Optional[str] = None) -> list[dict]:
    if file:
        rows = conn.execute(
            "SELECT * FROM sections WHERE file = ? ORDER BY line_start", (file,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM sections ORDER BY file, line_start"
        ).fetchall()
    return [dict(r) for r in rows]


def get_metadata(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute(
        "SELECT value FROM metadata WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else None


def set_metadata(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO metadata (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()


def get_stats(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) as c FROM sections").fetchone()["c"]
    files = conn.execute("SELECT COUNT(DISTINCT file) as c FROM sections").fetchone()["c"]
    return {"total_sections": total, "total_files": files}
