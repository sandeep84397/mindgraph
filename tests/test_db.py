"""Tests for the SQLite + FTS5 database layer."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.db import (
    delete_sections_for_file,
    delete_stale_sections,
    get_all_sections,
    get_connection,
    get_metadata,
    get_stats,
    search_fts,
    set_metadata,
    upsert_section,
)


@pytest.fixture
def db(tmp_path):
    conn = get_connection(tmp_path)
    yield conn
    conn.close()


@pytest.fixture
def seeded_db(db):
    """DB with some test sections."""
    upsert_section(db, "wiki/auth.md", "## Overview", 2, 1, 10,
                   "JWT auth middleware validate token reject expired",
                   "auth middleware handle JWT validation reject expired token pass user context",
                   "hash_auth_overview")
    upsert_section(db, "wiki/auth.md", "### Token Refresh", 3, 11, 25,
                   "token refresh use rotation strategy 24h expiry",
                   "refresh token rotate every 24 hour store in httponly cookie",
                   "hash_token_refresh")
    upsert_section(db, "wiki/database.md", "## Connection Pooling", 2, 1, 30,
                   "pgbouncer pool 20 max connection 30s timeout",
                   "connection pool use pgbouncer max 20 conn timeout 30s retry backoff",
                   "hash_db_pool")
    upsert_section(db, "wiki/database.md", "## Migrations", 2, 31, 50,
                   "alembic migration auto-generate from model diff",
                   "database migration use alembic auto-generate from sqlalchemy model diff",
                   "hash_db_migration")
    return db


class TestSchema:
    def test_connection(self, db):
        assert db is not None

    def test_tables_exist(self, db):
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r["name"] for r in tables}
        assert "sections" in names
        assert "sections_fts" in names
        assert "metadata" in names


class TestUpsert:
    def test_insert(self, db):
        rowid = upsert_section(db, "wiki/test.md", "## Heading", 2, 1, 10,
                               "brief", "fingerprint", "hash123")
        assert rowid > 0

    def test_update_on_conflict(self, db):
        upsert_section(db, "wiki/test.md", "## Heading", 2, 1, 10,
                       "brief_v1", "fp_v1", "hash_v1")
        upsert_section(db, "wiki/test.md", "## Heading", 2, 1, 15,
                       "brief_v2", "fp_v2", "hash_v2")
        rows = get_all_sections(db, "wiki/test.md")
        assert len(rows) == 1
        assert rows[0]["brief"] == "brief_v2"
        assert rows[0]["content_hash"] == "hash_v2"


class TestSearch:
    def test_fts_search(self, seeded_db):
        results = search_fts(seeded_db, "JWT auth middleware validate")
        assert len(results) > 0
        assert results[0]["file"] == "wiki/auth.md"

    def test_fts_database_query(self, seeded_db):
        results = search_fts(seeded_db, "pgbouncer connection pool")
        assert len(results) > 0
        assert results[0]["file"] == "wiki/database.md"

    def test_fts_no_results(self, seeded_db):
        results = search_fts(seeded_db, "quantum_computing_zxcvbnm")
        assert len(results) == 0

    def test_fts_limit(self, seeded_db):
        results = search_fts(seeded_db, "token", limit=1)
        assert len(results) <= 1


class TestDeleteStale:
    def test_remove_stale(self, seeded_db):
        # Keep only auth overview, remove token refresh
        removed = delete_stale_sections(
            seeded_db, "wiki/auth.md", {"hash_auth_overview"}
        )
        assert removed == 1
        remaining = get_all_sections(seeded_db, "wiki/auth.md")
        assert len(remaining) == 1

    def test_no_stale(self, seeded_db):
        removed = delete_stale_sections(
            seeded_db, "wiki/auth.md",
            {"hash_auth_overview", "hash_token_refresh"}
        )
        assert removed == 0


class TestDeleteFile:
    def test_delete_all_sections(self, seeded_db):
        removed = delete_sections_for_file(seeded_db, "wiki/auth.md")
        assert removed == 2
        remaining = get_all_sections(seeded_db, "wiki/auth.md")
        assert len(remaining) == 0


class TestMetadata:
    def test_set_get(self, db):
        set_metadata(db, "version", "1.0")
        assert get_metadata(db, "version") == "1.0"

    def test_update(self, db):
        set_metadata(db, "version", "1.0")
        set_metadata(db, "version", "2.0")
        assert get_metadata(db, "version") == "2.0"

    def test_missing_key(self, db):
        assert get_metadata(db, "nonexistent") is None


class TestStats:
    def test_stats(self, seeded_db):
        s = get_stats(seeded_db)
        assert s["total_sections"] == 4
        assert s["total_files"] == 2
