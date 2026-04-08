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

    # Project mode: create a CLAUDE.md snippet
    if mode == "project":
        claude_md = target / "CLAUDE.md"
        if not claude_md.exists():
            claude_md.write_text(CLAUDE_MD_SNIPPET, encoding="utf-8")
            created.append("CLAUDE.md")

    # Log initialization
    log_path = target / "wiki" / "log.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n[{now}] [INGEST] Knowledge base initialized (mode={mode})\n")

    return {"target": str(target), "mode": mode, "created": created}


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
    print(f"MindGraph initialized at {result['target']} (mode={result['mode']})")
    for item in result["created"]:
        print(f"  + {item}")


if __name__ == "__main__":
    main()
