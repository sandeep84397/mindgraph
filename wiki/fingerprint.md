Created `wiki/tools-fingerprint.md`. The page covers:

- **Entry points** — `fingerprint_file` and `fingerprint_all` with their responsibilities
- **Claude compression pipeline** — the three generation functions, input limits, and caveman style rules
- **Change detection** — content hash comparison logic and `--force` flag behavior
- **Stale/orphan cleanup** — how removed sections and deleted files are pruned from the DB
- **CLI usage** — the three invocation modes
