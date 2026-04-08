"""Tests for the lint tool."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.db import get_connection, upsert_section
from tools.lint import (
    lint_broken_links,
    lint_empty_sections,
    lint_missing_index,
    lint_orphan_db_entries,
    lint_staleness,
)


@pytest.fixture
def kb(tmp_path):
    """Create a minimal knowledge base structure."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (tmp_path / "raw").mkdir()
    (tmp_path / ".mindgraph").mkdir()

    # schema
    (wiki / "schema.md").write_text("# Schema\n")

    # index
    (wiki / "index.md").write_text(
        "# Index\n\n## Topics\n\n- [[Auth]]\n"
    )

    # log
    (wiki / "log.md").write_text("# Log\n")

    # A wiki page
    (wiki / "auth.md").write_text(
        "# Auth\n\n## Summary\n\nAuth system overview.\n\n"
        "## Details\n\nUses JWT tokens.\n\n"
        "## References\n\n- raw/auth_spec.md\n\n"
        "## See Also\n\n- [[Nonexistent Page]]\n- [[Database]]\n"
    )

    return tmp_path


@pytest.fixture
def kb_conn(kb):
    conn = get_connection(kb)
    yield kb, conn
    conn.close()


class TestStaleness:
    def test_detect_stale(self, kb_conn):
        kb, conn = kb_conn
        # Insert a section with wrong hash
        upsert_section(conn, "wiki/auth.md", "## Summary", 2, 3, 4,
                       "brief", "fp", "wrong_hash_that_wont_match")
        issues = lint_staleness(kb, conn)
        # Should detect stale sections (content changed)
        assert any(i.category == "stale" for i in issues)


class TestOrphans:
    def test_detect_orphan_db(self, kb_conn):
        kb, conn = kb_conn
        # Insert section for non-existent file
        upsert_section(conn, "wiki/deleted_page.md", "## Ghost", 2, 1, 5,
                       "brief", "fp", "hash")
        issues = lint_orphan_db_entries(kb, conn)
        assert len(issues) == 1
        assert issues[0].category == "orphan"
        assert "deleted_page.md" in issues[0].message


class TestBrokenLinks:
    def test_detect_broken_links(self, kb):
        issues = lint_broken_links(kb)
        broken = [i for i in issues if i.category == "broken_link"]
        # [[Nonexistent Page]] and [[Database]] should be broken
        assert len(broken) >= 1
        messages = " ".join(i.message for i in broken)
        assert "Nonexistent Page" in messages or "nonexistent_page" in messages


class TestMissingIndex:
    def test_detect_missing_from_index(self, kb):
        # Create a page not in index
        (kb / "wiki" / "secret_page.md").write_text("# Secret\n\n## Summary\n\nHidden.\n")
        issues = lint_missing_index(kb)
        missing = [i for i in issues if i.category == "missing_index"]
        assert any("secret_page" in i.file for i in missing)


class TestEmptySections:
    def test_detect_empty(self, kb):
        (kb / "wiki" / "empty_test.md").write_text(
            "# Test\n\n## Summary\n\n## Details\n\nContent here.\n"
        )
        issues = lint_empty_sections(kb)
        empty = [i for i in issues if i.category == "empty" and "empty_test" in i.file]
        assert any("Summary" in i.message for i in empty)
