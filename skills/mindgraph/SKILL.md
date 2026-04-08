---
name: mindgraph
description: >
  Fingerprinted knowledge graph with reactive indexing. Use when user says
  "create a mind map", "build knowledge base", "ingest this", "search my wiki",
  "what do I know about X", "mindgraph", or "/mindgraph". Also triggers on
  "knowledge graph", "mind map", "wiki", "index this project".
---

# MindGraph — Fingerprinted Knowledge Graph

You operate a three-layer knowledge system with real-time reactive indexing.

## Architecture

```
raw/           → Immutable source documents
wiki/          → LLM-compiled markdown articles (entity, topic, summary pages)
.mindgraph/    → SQLite + FTS5 fingerprint index (section-level)
```

The fingerprint index stores caveman-compressed briefs and section pointers.
You NEVER need to read entire wiki files — search the index first, read only matched sections.

## Tools

All tools run from the mindgraph plugin directory. Replace `<kb>` with the knowledge base root path.

| Command | Usage |
|---------|-------|
| init | `python3 -m tools init <kb> [--mode standalone\|project]` |
| ingest | `python3 -m tools ingest <kb> <source_file>` |
| fingerprint | `python3 -m tools fingerprint <kb> [--force] [--file path]` |
| search | `python3 -m tools search <kb> "query" [--limit N] [--verbose]` |
| lint | `python3 -m tools lint <kb> [--fix]` |
| watch start | `python3 -m tools watch <kb> start` |
| watch stop | `python3 -m tools watch <kb> stop` |
| watch status | `python3 -m tools watch <kb> status` |

## Workflows

### Initialize a Knowledge Base
When user says "create a mind map" or "start a knowledge base":
1. Ask: standalone or for this project?
2. Run: `python3 -m tools init <path> --mode <mode>`
3. Start the watcher: `python3 -m tools watch <path> start`
4. Explain the structure created

### Ingest a Source
When user provides a paper, article, URL, or says "ingest this":
1. If URL: download/save to raw/ first
2. Run: `python3 -m tools ingest <kb> <source_file>`
3. The tool compiles wiki pages, updates index/log, and fingerprints automatically
4. Report what was created

### Query the Knowledge Base
When user asks "what do I know about X" or any question:
1. **ALWAYS search first**: `python3 -m tools search <kb> "query terms"`
2. Read ONLY the matched file:line_range sections (not entire files)
3. Synthesize an answer from the matched sections
4. If the answer is valuable: suggest filing it as a new wiki page

### Lint and Maintain
When user says "check health" or you notice issues:
1. Run: `python3 -m tools lint <kb>`
2. Report issues found
3. Offer to fix: `python3 -m tools lint <kb> --fix`

### Real-Time Updates
The watcher daemon handles fingerprint updates automatically:
- File modified → changed sections re-fingerprinted
- New file created → wiki node auto-generated and fingerprinted
- File deleted → DB entries cleaned up
- No manual fingerprint step needed

## Rules

1. **Search before reading** — always query the fingerprint index first
2. **Read sections, not files** — use the line ranges from search results
3. **Trust the watcher** — don't manually fingerprint unless watcher is stopped
4. **Follow the schema** — wiki pages must have Summary, Details, References, See Also sections
5. **Log everything** — all operations get logged to wiki/log.md
6. **Cross-reference** — use [[Page Name]] links between wiki pages
7. **Caveman briefs** — index briefs are compressed; expand mentally when reading

## Token Efficiency Protocol

This system exists to minimize token waste across Claude sessions:
- The fingerprint index is ~20-50KB for hundreds of articles
- Each search returns only relevant section pointers
- You read specific line ranges, not entire 10KB+ wiki pages
- Multiple Claude sessions share the same index via .mindgraph/mindgraph.db
