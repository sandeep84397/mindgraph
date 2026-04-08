# Database Layer

## Summary
`tools/db.py` — SQLite + FTS5 persistence for MindGraph fingerprint index. `sections` table: parsed wiki headings, briefs, fingerprints. FTS5 virtual table synced via triggers.

## Details

### Schema

Three tables, created on first connect:

- **`sections`** — file path, heading text, heading level, line range, brief, fingerprint, content hash, timestamp. Unique index on `(file, heading, line_start)` deduplicates.
- **`sections_fts`** — FTS5 content table mirrors `brief` + `fingerprint` from `sections`. Triggers (`sections_ai`, `sections_ad`, `sections_au`) keep sync on insert/delete/update.
- **`metadata`** — key/value store for schema metadata.

### Connection Management

`get_connection(kb_root)` — single entry point. Resolves `.mindgraph/mindgraph.db`, creates dir if missing, enables WAL + foreign keys, calls `init_schema` to apply `SCHEMA_SQL` idempotently.

### Write Operations

| Function | Behavior |
|---|---|
| `upsert_section(...)` | INSERT or UPDATE by `(file, heading, line_start)`; returns `lastrowid` |
| `delete_sections_for_file(conn, file)` | Remove all sections for file |
| `delete_stale_sections(conn, file, valid_hashes)` | Remove sections where `content_hash` not in `valid_hashes` |

### Search

`search_fts(conn, query, limit)` — queries `sections_fts`, returns rows as dicts. Keyword search over briefs and fingerprints.

### Storage Location

Always at `<kb_root>/.mindgraph/mindgraph.db` (`DB_DIR`, `DB_NAME` constants).

## References
- `tools/db.py`

## See Also
- [[Schema]]
- [[Tools Init]]
- [[Tools Main]]
