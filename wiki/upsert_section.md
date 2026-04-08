# Upsert_Section

## Summary

Auto-learned from 7 file(s) matching: `upsert_section`

## Details

### tests/test_db.py

- L18: `upsert_section,`
- L32: `upsert_section(db, "wiki/auth.md", "## Overview", 2, 1, 10,`
- L36: `upsert_section(db, "wiki/auth.md", "### Token Refresh", 3, 11, 25,`
- L40: `upsert_section(db, "wiki/database.md", "## Connection Pooling", 2, 1, 30,`
- L44: `upsert_section(db, "wiki/database.md", "## Migrations", 2, 31, 50,`

### tests/test_lint.py

- L9: `from tools.db import get_connection, upsert_section`
- L60: `upsert_section(conn, "wiki/auth.md", "## Summary", 2, 3, 4,`
- L71: `upsert_section(conn, "wiki/deleted_page.md", "## Ghost", 2, 1, 5,`

### tools/db.py

- L76: `def upsert_section(`

### tools/fingerprint.py

- L12: `upsert_section,`
- L146: `upsert_section(`

### tools/learn.py

- L16: `from tools.db import get_connection, get_all_sections, search_fts, upsert_section`
- L274: `upsert_section(`

### wiki/db.md

- L1: `Created `wiki/tools-db.md`. The page covers the FTS5 schema and triggers, connection setup with WAL/FK pragmas, the thre`

### wiki/tools-db.md

- L24: `| `upsert_section(...)` | INSERT or UPDATE by `(file, heading, line_start)`; returns `lastrowid` |`


## References

- `tests/test_db.py`
- `tests/test_lint.py`
- `tools/db.py`
- `tools/fingerprint.py`
- `tools/learn.py`
- `wiki/db.md`
- `wiki/tools-db.md`

## See Also

<!-- Cross-references will be added as the graph grows -->
