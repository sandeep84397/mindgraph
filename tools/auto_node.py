"""Auto-create wiki nodes for new files detected by the watcher."""
from __future__ import annotations
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tools.ingest import append_log, slugify, update_index


def detect_file_type(filepath: Path) -> str:
    """Detect whether a file is code, markdown, data, or other."""
    ext = filepath.suffix.lower()
    code_exts = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
                 ".c", ".cpp", ".h", ".rb", ".swift", ".kt", ".cs", ".sh"}
    md_exts = {".md", ".markdown", ".rst", ".txt"}
    data_exts = {".json", ".yaml", ".yml", ".toml", ".csv", ".xml"}

    if ext in code_exts:
        return "code"
    elif ext in md_exts:
        return "markdown"
    elif ext in data_exts:
        return "data"
    return "other"


def extract_code_structure(content: str, ext: str) -> list[str]:
    """Extract top-level function/class names from code for section headings."""
    headings = []
    if ext in (".py",):
        for match in re.finditer(r"^(?:class|def)\s+(\w+)", content, re.MULTILINE):
            headings.append(match.group(1))
    elif ext in (".js", ".ts", ".tsx", ".jsx"):
        for match in re.finditer(
            r"^(?:export\s+)?(?:function|class|const|let)\s+(\w+)", content, re.MULTILINE
        ):
            headings.append(match.group(1))
    elif ext in (".go",):
        for match in re.finditer(r"^(?:func|type)\s+(\w+)", content, re.MULTILINE):
            headings.append(match.group(1))
    return headings[:20]  # cap at 20


def generate_wiki_stub(filepath: Path, kb_root: Path) -> tuple[str, str]:
    """Generate a wiki page for a new file.

    Returns: (filename, content) for the wiki page.
    """
    file_type = detect_file_type(filepath)
    name = filepath.stem
    slug = slugify(name)
    rel_path = str(filepath.relative_to(kb_root)) if str(filepath).startswith(str(kb_root)) else str(filepath)

    try:
        content = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, PermissionError):
        content = f"[Binary or unreadable file: {filepath.name}]"

    # Try Claude for richer generation
    wiki_content = _generate_via_claude(filepath.name, file_type, content[:4000], rel_path)
    if wiki_content:
        return f"{slug}.md", wiki_content

    # Fallback: structured stub
    sections = []
    sections.append(f"# {name}\n")
    sections.append(f"## Summary\n\n{file_type.title()} file: `{rel_path}`\n")
    sections.append("## Details\n")

    if file_type == "code":
        headings = extract_code_structure(content, filepath.suffix.lower())
        if headings:
            for h in headings:
                sections.append(f"### {h}\n\n<!-- Auto-generated stub -->\n")
        else:
            sections.append(f"\n```{filepath.suffix.lstrip('.')}\n{content[:1000]}\n```\n")
    elif file_type == "markdown":
        sections.append(f"\n{content[:2000]}\n")
    else:
        sections.append(f"\nFile type: {file_type}\n")

    sections.append(f"\n## References\n\n- `{rel_path}`\n")
    sections.append("\n## See Also\n\n<!-- Add cross-references -->\n")

    return f"{slug}.md", "\n".join(sections)


def _generate_via_claude(filename: str, file_type: str, content: str, rel_path: str) -> Optional[str]:
    """Try to generate a wiki page via claude --print."""
    prompt = f"""Create a wiki page for this {file_type} file. Follow this format exactly:

# {{Title}}

## Summary
2-3 sentence overview.

## Details
Main content with ### subsections for key components.

## References
- `{rel_path}`

## See Also
Cross-references as [[Page Name]]

FILE: {filename}
---
{content}"""

    try:
        result = subprocess.run(
            ["claude", "--print", "-p", prompt],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip() + "\n"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def auto_create_node(filepath: Path, kb_root: Path) -> Optional[dict]:
    """Create or update a wiki node for a source file.

    - Creates a new wiki page if one doesn't exist.
    - Regenerates the wiki page if the source file has changed.
    - Returns None if file should be skipped (is in wiki/).
    """
    wiki_dir = kb_root / "wiki"

    # Don't create wiki pages for wiki files themselves
    try:
        filepath.relative_to(wiki_dir)
        return None
    except ValueError:
        pass

    slug = slugify(filepath.stem)
    wiki_path = wiki_dir / f"{slug}.md"
    is_update = wiki_path.exists()

    filename, content = generate_wiki_stub(filepath, kb_root)
    wiki_path = wiki_dir / filename
    wiki_path.write_text(content, encoding="utf-8")

    if not is_update:
        update_index(kb_root, [filename])
    action = "Updated" if is_update else "Auto-created"
    append_log(kb_root, "AUTO", f"{action} wiki node for {filepath.name} → wiki/{filename}")

    # Fingerprint the new/updated page
    from tools.db import get_connection
    from tools.fingerprint import fingerprint_file

    conn = get_connection(kb_root)
    stats = fingerprint_file(kb_root, wiki_path, conn, force=is_update)
    conn.close()

    return {"wiki_page": filename, "sections": stats["new"] + stats["updated"], "updated": is_update}
