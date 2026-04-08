# Auto Node

## Summary
`tools/auto_node.py` generates wiki stub pages automatically when the file watcher detects new files. It classifies files by type, extracts structural metadata from code, and delegates to the Claude CLI for richer content generation with a structured fallback.

## Details

### detect_file_type
Classifies a file as `"code"`, `"markdown"`, `"data"`, or `"other"` based on its extension. Used to drive downstream formatting decisions in `generate_wiki_stub`.

| Type | Extensions |
|---|---|
| `code` | `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.go`, `.rs`, `.java`, `.c`, `.cpp`, `.h`, `.rb`, `.swift`, `.kt`, `.cs`, `.sh` |
| `markdown` | `.md`, `.markdown`, `.rst`, `.txt` |
| `data` | `.json`, `.yaml`, `.yml`, `.toml`, `.csv`, `.xml` |
| `other` | everything else |

### extract_code_structure
Parses the raw file content with regex to extract top-level definition names (functions, classes, constants). Returns up to 20 names, used as `###` subsection headings in the fallback stub.

| Language | Patterns matched |
|---|---|
| Python | `class` / `def` at line start |
| JS/TS/JSX/TSX | `export? function\|class\|const\|let` at line start |
| Go | `func` / `type` at line start |

### generate_wiki_stub
Main entry point. Reads the target file, calls `_generate_via_claude` first; if that fails, builds a structured stub from the file type and extracted headings. Returns `(filename, content)` where `filename` is the slugified wiki page name.

Fallback stub structure:
1. `# {stem}` title
2. `## Summary` — file type and relative path
3. `## Details` — code headings, raw markdown content, or file-type label
4. `## References` — relative path
5. `## See Also` — placeholder comment

### _generate_via_claude
Runs `claude --print -p <prompt>` as a subprocess (60 s timeout). The prompt uses the same wiki format required by this project. Returns the stdout on success, `None` on any failure (non-zero exit, timeout, `FileNotFoundError`).

## References
- `tools/auto_node.py`

## See Also
- [[Tools Watch]]
- [[Tools Ingest]]
- [[MindGraph Schema]]
