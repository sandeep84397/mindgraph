"""Initialize a MindGraph knowledge base."""
import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

from tools.db import get_connection

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def init_knowledge_base(target: Path, mode: str = "standalone") -> dict:
    """Scaffold a MindGraph knowledge base at the target directory.

    Creates: raw/, wiki/, .mindgraph/mindgraph.db, and template files.
    Returns summary of what was created.
    """
    created = []

    # Create directories
    for d in ["raw", "wiki", ".mindgraph"]:
        (target / d).mkdir(parents=True, exist_ok=True)
        created.append(f"{d}/")

    # Copy templates
    for template in ["schema.md", "index.md", "log.md"]:
        src = TEMPLATES_DIR / template
        dst = target / "wiki" / template
        if not dst.exists():
            shutil.copy2(src, dst)
            created.append(f"wiki/{template}")

    # Initialize database
    conn = get_connection(target)
    conn.close()
    created.append(".mindgraph/mindgraph.db")

    # Project mode: create a CLAUDE.md snippet + scan source files
    if mode == "project":
        claude_md = target / "CLAUDE.md"
        if not claude_md.exists():
            claude_md.write_text(CLAUDE_MD_SNIPPET, encoding="utf-8")
            created.append("CLAUDE.md")

        # Scan project source files and create wiki nodes
        wiki_nodes = _scan_project_sources(target)
        created.extend(wiki_nodes)

    # Log initialization
    log_path = target / "wiki" / "log.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n[{now}] [INGEST] Knowledge base initialized (mode={mode})\n")

    return {"target": str(target), "mode": mode, "created": created}


# Extensions to scan during project init
_SOURCE_EXTS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".rb", ".swift", ".kt", ".cs", ".sh",
    ".yaml", ".yml", ".json", ".toml",
}

# Directories to skip during scan
_SKIP_DIRS = {
    ".git", ".mindgraph", ".venv", "venv", "node_modules", "__pycache__",
    "dist", "build", ".next", ".nuxt", "target", "bin", "obj",
    "wiki", "raw", ".claude", ".idea", ".vscode",
}


def _scan_project_sources(target: Path) -> list[str]:
    """Scan the project for source files and create wiki nodes for each.

    Returns list of created wiki page paths (e.g., 'wiki/my_module.md').
    """
    from tools.auto_node import auto_create_node

    source_files = []
    for path in sorted(target.rglob("*")):
        if not path.is_file():
            continue
        # Skip files in ignored directories
        if any(part in _SKIP_DIRS for part in path.relative_to(target).parts):
            continue
        if path.suffix.lower() in _SOURCE_EXTS:
            source_files.append(path)

    created = []
    for filepath in source_files:
        result = auto_create_node(filepath, target)
        if result:
            created.append(f"wiki/{result['wiki_page']}")

    return created


CLAUDE_MD_SNIPPET = """## MindGraph Knowledge Base

This project has a MindGraph knowledge base at `.mindgraph/`.

### Search before reading
Before exploring code with Grep/Glob, search the knowledge graph first:
```bash
python3 -m tools search . "your query"
```

### After modifying wiki files
The watcher daemon auto-updates fingerprints. If not running:
```bash
python3 -m tools fingerprint .
```

### Available commands
| Command | Usage |
|---------|-------|
| search | `python3 -m tools search . "query"` |
| fingerprint | `python3 -m tools fingerprint .` |
| ingest | `python3 -m tools ingest . <source>` |
| lint | `python3 -m tools lint .` |
| watch | `python3 -m tools watch . start` |
"""


def main():
    parser = argparse.ArgumentParser(description="Initialize a MindGraph knowledge base")
    parser.add_argument("target", help="Directory to create the knowledge base in")
    parser.add_argument(
        "--mode",
        choices=["standalone", "project"],
        default="standalone",
        help="standalone = self-contained KB, project = add to existing codebase",
    )
    args = parser.parse_args()
    target = Path(args.target).resolve()
    result = init_knowledge_base(target, args.mode)
    wiki_nodes = [c for c in result["created"] if c.startswith("wiki/") and c != "wiki/"]
    scaffolding = [c for c in result["created"] if c not in wiki_nodes]
    print(f"MindGraph initialized at {result['target']} (mode={result['mode']})")
    for item in scaffolding:
        print(f"  + {item}")
    if wiki_nodes:
        print(f"  + {len(wiki_nodes)} wiki nodes created from project source files")


if __name__ == "__main__":
    main()
