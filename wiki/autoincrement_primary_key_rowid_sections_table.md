# Autoincrement Primary Key Rowid Sections Table

## Summary

Auto-learned from 1 file(s) matching: `please explain how the AUTOINCREMENT primary key and rowid relationship works in the sections table`

## Details

### tools/db.py

- L12: `CREATE TABLE IF NOT EXISTS sections (`
- L13: `id INTEGER PRIMARY KEY AUTOINCREMENT,`
- L25: `CREATE UNIQUE INDEX IF NOT EXISTS idx_sections_file_heading_line`
- L26: `ON sections(file, heading, line_start);`
- L28: `CREATE VIRTUAL TABLE IF NOT EXISTS sections_fts USING fts5(`


## References

- `tools/db.py`

## See Also

<!-- Cross-references will be added as the graph grows -->
