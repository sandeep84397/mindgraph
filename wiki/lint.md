# Lint

Detect stale fingerprints, orphans, broken links. Entry: `tools/lint.py`.

## Run

```bash
python3 -m tools lint .
python3 -m tools lint . --fix
```

## `LintIssue`

Dataclass. Fields: `severity` (`error`|`warning`|`info`), `category`, `file`, `line`, `message`.

## Checks

### `lint_staleness`

Severity: `warning`. Scan `wiki/**/*.md`. Recompute hash per section. Hash not in DB → stale.

### `lint_orphan_db_entries`

Severity: `error`. DB has sections for file not on disk → orphan.

### `lint_broken_links`

Severity: `warning`. Find `[[Page Name]]`. Check `wiki/<slug>.md` exists. Missing → broken link.

### `lint_missing_index`

Severity: `info`. Page stem not in `wiki/index.md` → unlisted.

### `lint_empty_sections`

Severity: `info`. Section body empty after heading → empty.

## `SKIP_FILES`

```python
SKIP_FILES = {"schema.md", "index.md", "log.md"}
```

All checks skip these files.

## Auto-fix (`--fix`)

Fix stale: re-fingerprint via `tools/fingerprint.py:fingerprint_file`. Fix orphan: `tools/db.py:delete_sections_for_file`. Other categories not fixable.

## Related

- [[Fingerprint]] — `tools/fingerprint.py`
- [[DB]] — `tools/db.py`
- [[Parser]] — `tools/parser.py`
