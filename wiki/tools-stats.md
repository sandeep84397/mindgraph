# Tools: Stats

## Summary
`tools/stats.py` calculate token savings: MindGraph fingerprint index vs reading full source files. Compare three token cost levels — full file, section-level, compressed brief — quantify context saved per search. Track cumulative savings across searches.

## Details

### Token Estimation

`CHARS_PER_TOKEN = 4` converts char counts to token estimates. `estimate_tokens(text)` applies ratio, minimum 1.

### `compute_savings(kb_root)`

Primary function. Pull all sections and file metadata from SQLite, compute:

- **`full_file_tokens`** — tokens if Claude read every tracked file in full
- **`section_tokens`** — tokens for matched line ranges (~40 chars/line)
- **`brief_tokens`** — tokens for compressed summaries per section
- **`tokens_saved_per_search`** — avg savings per search: `avg_file_tokens - (avg_section_tokens + avg_brief_tokens)`
- **`compression_ratio`** — `full_file_tokens / brief_tokens`
- **`cumulative_searches` / `cumulative_tokens_saved`** — running totals from `metadata` table

Return dict with all metrics. Return zeroed defaults if no sections.

### `record_search(kb_root, sections_returned)`

Call after each search. Increment cumulative counters in DB. Recompute avg tokens per file and section, update `cumulative_searches` and `cumulative_tokens_saved` via `set_metadata`.

### CLI (`__main__` integration)

`python3 -m tools stats .` — call `compute_savings`, print formatted JSON.

## References
- `tools/stats.py`

## See Also
- [[Tools: DB]] — `get_connection`, `get_all_sections`, `get_stats`, `get_metadata`, `set_metadata`
- [[Tools: Search]] — calls `record_search` after returning results
- [[Tools: Main]] — CLI entry point dispatches `stats` subcommand
