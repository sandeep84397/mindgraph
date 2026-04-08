# Fingerprint

## Summary
`tools/fingerprint.py` — build/rebuild SQLite fingerprint index from wiki markdown. Parse sections, generate Claude-compressed briefs+fingerprints, upsert changed records, prune stale/orphaned entries.

## Details

### Entry Points

- **`fingerprint_file(kb_root, wiki_file, conn, force)`** — process single `.md`: parse sections, check content hashes vs DB, generate briefs/fingerprints for changed sections only, remove stale sections.
- **`fingerprint_all(kb_root, force)`** — glob `wiki/**/*.md`, skip `SKIP_FILES`, call `fingerprint_file` each, remove orphaned sections for deleted files. Write `last_fingerprint` timestamp to metadata.

`SKIP_FILES = {"schema.md", "index.md", "log.md"}` — never indexed.

### Claude Compression Pipeline

Use Claude CLI (`claude --print`) for token-efficient representations:

| Function | Output | Input limit |
|---|---|---|
| `generate_brief(section)` | 1-line caveman summary | 2000 chars |
| `batch_generate_briefs(sections, batch_size=10)` | List of briefs via single Claude call | 1000 chars/section |
| `generate_fingerprint(section)` | Full caveman-compressed section | 4000 chars |

`call_claude_print(prompt)` — subprocess wrapper around `claude --print -p <prompt>`, 30s timeout. Fail → empty string; callers fall back to truncated raw content.

**Caveman style**: drop articles, filler, hedging; preserve code blocks, URLs, paths, technical terms exactly.

### Change Detection

`fingerprint_file` skip redundant Claude calls via content hash:

1. `compute_content_hash(section.content)` — hash each parsed section.
2. Check existing DB row by `(file, heading, line_start)`.
3. Queue for Claude only sections with missing/mismatched `content_hash`.
4. `--force` — bypass check, re-fingerprint everything.

### Stale / Orphan Cleanup

- **Stale sections**: after file process, `delete_stale_sections(conn, file, valid_hashes)` remove DB rows with `content_hash` no longer in file.
- **Orphan files**: `fingerprint_all` diff `wiki/**/*.md` on disk vs `DISTINCT file` in DB; purge sections for deleted files.

### CLI

```
python3 -m tools fingerprint <kb_root> [--force] [--file <path>]
```

- No `--file`: fingerprint all wiki files.
- `--file`: fingerprint one file; path absolute or relative to `kb_root`.
- `--force`: re-generate briefs/fingerprints all sections, ignore hash.

## References
- `tools/fingerprint.py`

## See Also
- [[Database Layer]]
- [[Tools Main]]
- [[Tools Init]]
