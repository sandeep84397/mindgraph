# MindGraph Skill

## Summary
Fingerprinted knowledge graph + reactive indexing for Claude Code. Three-layer system: raw sources, compiled wiki articles, SQLite+FTS5 index. Token-efficient retrieval across sessions. Triggers: "create a mind map", "build knowledge base", "search my wiki", "what do I know about X".

## Details

### Architecture

Three storage layers:

- **`raw/`** — Immutable source docs (papers, articles, ingested files)
- **`wiki/`** — LLM-compiled markdown articles: entity, topic, summary pages
- **`.mindgraph/`** — SQLite+FTS5 fingerprint index: caveman briefs + section pointers

Index ~20–50KB for hundreds of articles. Multiple Claude sessions share `.mindgraph/mindgraph.db`. No re-reading full files.

### CLI Tools

All tools: `python3 -m tools <command> <kb> [args]`. `<kb>` = knowledge base root path.

| Command | Usage |
|---------|-------|
| `init` | `python3 -m tools init <kb> [--mode standalone\|project]` |
| `ingest` | `python3 -m tools ingest <kb> <source_file>` |
| `fingerprint` | `python3 -m tools fingerprint <kb> [--force] [--file path]` |
| `search` | `python3 -m tools search <kb> "query" [--limit N] [--verbose]` |
| `lint` | `python3 -m tools lint <kb> [--fix]` |
| `stats` | `python3 -m tools stats <kb> [--json]` |
| `watch start/stop/status` | `python3 -m tools watch <kb> start\|stop\|status` |

### Workflows

#### Initialize Knowledge Base
Triggers: "create a mind map", "start a knowledge base":
1. Ask: standalone or project?
2. Run `init` with mode
3. Start watcher daemon
4. Explain structure

#### Ingest Source
Triggers: user gives paper, article, URL, "ingest this":
1. URL → download, save to `raw/` first
2. Run `ingest` — compiles wiki pages, updates index/log, fingerprints

#### Query Knowledge Base
Triggers: "what do I know about X", any KB question:
1. Search first: `python3 -m tools search <kb> "query"`
2. Read matched `file:line_range` sections only
3. Synthesize answer; offer to file new wiki page if valuable

#### Lint and Maintain
Triggers: "check health", observed issues:
1. Run `lint` — report issues
2. Offer `--fix`

### Watcher Daemon
Handles fingerprint updates:
- Modified file → changed sections re-fingerprinted
- New file → auto wiki node + fingerprinted
- Deleted file → DB entries cleaned

### Token Efficiency Protocol
- Search returns section pointers only — not full file contents
- Index briefs caveman-compressed; expand mentally
- Read line ranges from search results — never entire wiki files

### Rules
1. Search before reading — query index first
2. Read sections not files — use line ranges from search results
3. Trust watcher — no manual fingerprinting unless watcher stopped
4. Follow schema — wiki pages need Summary, Details, References, See Also
5. Log everything — all ops logged to `wiki/log.md`
6. Cross-reference — use `[[Page Name]]` links between wiki pages

## References
- `skills/mindgraph/SKILL.md`

## See Also
- [[Fingerprint]]
- [[Ingest]]
- [[Search]]
- [[Lint]]
- [[Watch]]
- [[Init KB]]
- [[Schema]]
