## parser

**File:** `tools/parser.py`

Split `.md` files into sections on h2/h3 boundaries. Used by fingerprint pipeline.

---

## Section dataclass

```python
@dataclass
class Section:
    heading: str        # full heading text, e.g. "## Foo" or "## (preamble)"
    heading_level: int  # 2 or 3
    line_start: int     # 1-indexed, inclusive
    line_end: int       # 1-indexed, inclusive
    content: str        # raw lines joined with "\n", includes heading line
```

Fields `line_start`/`line_end` count from 1. `content` includes heading line itself.

---

## parse_sections

```python
def parse_sections(filepath: Path) -> list[Section]
```

Read file, split on h2/h3 headings, return ordered `Section` list.

### Preamble handling

Content before first heading → section with `heading="## (preamble)"`, `heading_level=2`. Empty preamble (whitespace only) skipped — not appended.

### Code fence skipping

Toggle `in_code_block` on ` ``` ` lines. Inside fence, `#` chars ignored — not treated as headings.

### Heading level rules

Only h2 (`## `) and h3 (`### `) trigger splits. h4+ ignored.

Detection order matters:
1. `### ` but not `#### ` → level 3
2. `## ` but not `### ` → level 2

New heading flushes previous section if `current_lines` non-empty OR heading is preamble sentinel.

### Final flush

After loop ends, remaining `current_lines` flushed as last section. Empty (whitespace-only) sections dropped.

---

## compute_content_hash

```python
def compute_content_hash(content: str) -> str
```

SHA-256 of `content` encoded UTF-8. Returns hex digest. Used by fingerprint pipeline to detect section changes.

---

## See also

- [fingerprint](fingerprint.md) — calls `parse_sections`, stores hashes per section
- [db](db.md) — stores `Section` data in SQLite
- [ingest](ingest.md) — uses parser for external source ingestion
- [lint](lint.md) — uses `parse_sections` to validate section structure
