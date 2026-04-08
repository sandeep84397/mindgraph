# Tools Ingest

## Summary
`tools/ingest.py` eat source file. Copy to `raw/`, call Claude make wiki pages, update index and log. Claude unavailable or timeout? Make minimal fallback page.

## Details

### Entry Points

`ingest_source(kb_root, source_path)` main function. Do pipeline:
1. Copy source to `raw/`
2. Read source, read wiki schema
3. Load existing wiki page names
4. Call `compile_wiki_pages()` get pages from Claude
5. Write pages to `wiki/`
6. Update `wiki/index.md`, append `wiki/log.md`
7. Run `python3 -m tools fingerprint` on new pages

### `compile_wiki_pages`
Build prompt from schema, page list, source (truncate 8000 chars). Run `claude --print -p <prompt>` via `subprocess.run`, 120s timeout. Parse with `parse_compiled_output`. `FileNotFoundError` or `TimeoutExpired`? Return minimal page.

### `parse_compiled_output`
Parse `===PAGE: filename.md=== ... ===END===` blocks from Claude output. Use `re.DOTALL` regex. Return `{filename: content}`.

### `slugify`
Lowercase, strip non-word chars, replace whitespace/hyphens with underscores. Make wiki-safe filename.

### `read_source`
Read source as UTF-8. `UnicodeDecodeError`? Return `[Binary file: ...]`.

### `update_index`
Append `[[Page Name]]` links for new pages to `wiki/index.md`.

### `append_log`
Append timestamped entry `[YYYY-MM-DD HH:MM] [ACTION] description` to `wiki/log.md`.

## References
- `tools/ingest.py`

## See Also
- [[Tools Main]]
- [[Wiki Schema]]
- [[Tools Fingerprint]]
