---
name: mindgraph
description: >
  Fingerprinted knowledge graph with reactive indexing. Use when user says
  "create a mind map", "build knowledge base", "ingest this", "search my wiki",
  "what do I know about X", "mindgraph", or "/mindgraph". Also triggers on
  "knowledge graph", "mind map", "wiki", "index this project".
---

# MindGraph — Fingerprinted Knowledge Graph

Three-layer knowledge system. Reactive indexing.

## Architecture

```
raw/           → Immutable source documents
wiki/          → LLM-compiled markdown articles (entity, topic, summary pages)
.mindgraph/    → SQLite + FTS5 fingerprint index (section-level)
```

Index: caveman briefs + section pointers. NEVER read whole wiki files — search first, read matched sections only.

## Tools

`<kb>` = knowledge base root path.

| Command | Usage |
|---------|-------|
| init | `python3 -m tools init <kb> [--mode standalone\|project]` |
| ingest | `python3 -m tools ingest <kb> <source_file>` |
| fingerprint | `python3 -m tools fingerprint <kb> [--force] [--file path]` |
| search | `python3 -m tools search <kb> "query" [--limit N] [--verbose]` |
| lint | `python3 -m tools lint <kb> [--fix]` |
| stats | `python3 -m tools stats <kb> [--json]` |
| learn | `python3 -m tools learn <kb> "topic" [--json]` |
| watch start | `python3 -m tools watch <kb> start` |
| watch stop | `python3 -m tools watch <kb> stop` |
| watch status | `python3 -m tools watch <kb> status` |

## Workflows

### Initialize Knowledge Base
User: "create mind map" / "start knowledge base":
1. Ask: standalone or project?
2. Run: `python3 -m tools init <path> --mode <mode>`
3. Start watcher: `python3 -m tools watch <path> start`
4. Report structure created

### Ingest Source
User gives paper, article, URL, "ingest this":
1. URL: download → save to raw/ first
2. Run: `python3 -m tools ingest <kb> <source_file>`
3. Tool compiles wiki pages, updates index/log, fingerprints
4. Report what created

### Query Knowledge Base
User asks "what do I know about X":
1. **Search first**: `python3 -m tools search <kb> "query terms"`
2. Read ONLY matched file:line_range sections
3. Synthesize from matched sections
4. Good answer: suggest new wiki page

### Lint and Maintain
User: "check health" / issues noticed:
1. Run: `python3 -m tools lint <kb>`
2. Report issues
3. Offer fix: `python3 -m tools lint <kb> --fix`

### Real-Time Updates
Watcher handles fingerprints:
- File modified → changed sections re-fingerprinted
- New file → wiki node auto-generated + fingerprinted
- File deleted → DB entries cleaned
- No manual fingerprint needed

## Rules

1. **Search before reading** — query fingerprint index first
2. **Read sections, not files** — use line ranges from search results
3. **Trust watcher** — no manual fingerprint unless watcher stopped
4. **Follow schema** — wiki pages need Summary, Details, References, See Also
5. **Log everything** — all ops logged to wiki/log.md
6. **Cross-reference** — use [[Page Name]] links between wiki pages
7. **Caveman briefs** — index briefs compressed; expand mentally when reading

## Token Efficiency

- Fingerprint index ~20-50KB for hundreds of articles
- Search returns relevant section pointers only
- Read specific line ranges, not whole 10KB+ wiki pages
- Multiple Claude sessions share index via .mindgraph/mindgraph.db
