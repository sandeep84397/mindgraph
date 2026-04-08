# File Extensions Watcher

## Summary

Auto-learned from 2 file(s) matching: `what are all the different file extensions handled by the watcher`

## Details

### tools/db.py

- L14: `file TEXT NOT NULL,`
- L25: `CREATE UNIQUE INDEX IF NOT EXISTS idx_sections_file_heading_line`
- L26: `ON sections(file, heading, line_start);`
- L78: `file: str,`
- L89: `"""INSERT INTO sections (file, heading, heading_level, line_start, line_end,`

### tools/ingest.py

- L12: `"""Convert a name to a wiki-safe filename slug."""`
- L20: `"""Read source file content. Supports .md, .txt, and attempts others."""`
- L24: `return f"[Binary file: {source_path.name}]"`
- L32: `Returns: {filename: content} dict of wiki pages to create/update.`
- L50: `===PAGE: filename.md===`


## References

- `tools/db.py`
- `tools/ingest.py`

## See Also

<!-- Cross-references will be added as the graph grows -->
