"""Ingest raw sources into the MindGraph knowledge base."""
from __future__ import annotations
import argparse
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def slugify(name: str) -> str:
    """Convert a name to a wiki-safe filename slug."""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s-]+", "_", name)
    return name


def read_source(source_path: Path) -> str:
    """Read source file content. Supports .md, .txt, and attempts others."""
    try:
        return source_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"[Binary file: {source_path.name}]"


def compile_wiki_pages(
    source_content: str, source_name: str, schema: str, existing_pages: list[str]
) -> dict[str, str]:
    """Use claude --print to compile wiki pages from a source.

    Returns: {filename: content} dict of wiki pages to create/update.
    """
    existing_list = "\n".join(f"- {p}" for p in existing_pages) if existing_pages else "(none yet)"

    prompt = f"""You are compiling a knowledge base wiki. Read this source material and create wiki pages.

SCHEMA RULES:
{schema}

EXISTING WIKI PAGES (link to these with [[Page Name]] where relevant):
{existing_list}

SOURCE: {source_name}
---
{source_content[:8000]}
---

OUTPUT FORMAT: For each wiki page, output:
===PAGE: filename.md===
(page content following schema rules)
===END===

Create entity pages for key concepts and a summary page for this source. Use [[Page Name]] for cross-references."""

    try:
        result = subprocess.run(
            ["claude", "--print", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return parse_compiled_output(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: create a single summary page
    slug = slugify(source_name)
    return {
        f"summary_{slug}.md": f"""# {source_name}

## Summary

Source document ingested into knowledge base.

## Details

{source_content[:2000]}

## References

- raw/{source_name}

## See Also

<!-- Add cross-references as the knowledge base grows -->
"""
    }


def parse_compiled_output(output: str) -> dict[str, str]:
    """Parse ===PAGE: filename.md=== ... ===END=== blocks."""
    pages = {}
    pattern = r"===PAGE:\s*(.+?)===\s*\n(.*?)===END==="
    for match in re.finditer(pattern, output, re.DOTALL):
        filename = match.group(1).strip()
        content = match.group(2).strip() + "\n"
        pages[filename] = content
    return pages


def update_index(kb_root: Path, new_pages: list[str]) -> None:
    """Append new pages to wiki/index.md under Uncategorized."""
    index_path = kb_root / "wiki" / "index.md"
    if not index_path.exists():
        return
    content = index_path.read_text(encoding="utf-8")
    additions = "\n".join(
        f"- [[{p.replace('.md', '').replace('_', ' ').title()}]]"
        for p in new_pages
    )
    content = content.rstrip() + "\n" + additions + "\n"
    index_path.write_text(content, encoding="utf-8")


def append_log(kb_root: Path, action: str, description: str) -> None:
    """Append an entry to wiki/log.md."""
    log_path = kb_root / "wiki" / "log.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n[{now}] [{action}] {description}\n")


def ingest_source(kb_root: Path, source_path: Path, no_compile: bool = False) -> dict:
    """Ingest a raw source into the knowledge base.

    1. Copy to raw/
    2. Read source + schema
    3. Compile wiki pages via Claude (or use fallback template if no_compile)
    4. Dedup against existing pages
    5. Write pages, update index, log
    6. Fingerprint new pages
    """
    # 1. Copy source to raw/
    raw_dir = kb_root / "raw"
    raw_dir.mkdir(exist_ok=True)
    dest = raw_dir / source_path.name
    if not dest.exists():
        shutil.copy2(source_path, dest)

    # 2. Read source and schema
    source_content = read_source(source_path)
    schema_path = kb_root / "wiki" / "schema.md"
    schema = schema_path.read_text(encoding="utf-8") if schema_path.exists() else ""

    existing_pages = [
        f.stem for f in (kb_root / "wiki").glob("*.md")
        if f.name not in {"schema.md", "index.md", "log.md"}
    ]

    # 3. Compile wiki pages (skip LLM if --no-compile)
    if no_compile:
        slug = slugify(source_path.stem)
        pages = {
            f"{slug}.md": f"""# {source_path.stem}

## Summary

Source document ingested into knowledge base.

## Details

{source_content[:4000]}

## References

- raw/{source_path.name}

## See Also

<!-- Add cross-references as the knowledge base grows -->
"""
        }
    else:
        pages = compile_wiki_pages(source_content, source_path.name, schema, existing_pages)

    # 4. Dedup check — skip pages whose slug is too similar to an existing page
    from difflib import SequenceMatcher
    existing_slugs = {slugify(stem): stem for stem in existing_pages}
    deduped_pages = {}
    skipped = []
    for filename, content in pages.items():
        new_slug = filename.replace(".md", "")
        duplicate = False
        for ex_slug in existing_slugs:
            if SequenceMatcher(None, new_slug, ex_slug).ratio() >= 0.75:
                skipped.append((filename, ex_slug))
                duplicate = True
                break
        if not duplicate:
            deduped_pages[filename] = content
    pages = deduped_pages

    # 5. Write pages
    created = []
    updated = []
    wiki_dir = kb_root / "wiki"
    for filename, content in pages.items():
        filepath = wiki_dir / filename
        if filepath.exists():
            updated.append(filename)
        else:
            created.append(filename)
        filepath.write_text(content, encoding="utf-8")

    # 6. Update index and log
    if created:
        update_index(kb_root, created)
    page_names = ", ".join(created + updated)
    skip_msg = f" (skipped {len(skipped)} duplicates)" if skipped else ""
    append_log(kb_root, "INGEST", f"Ingested {source_path.name} → {page_names}{skip_msg}")

    # 6. Fingerprint new/updated pages
    from tools.fingerprint import fingerprint_file
    from tools.db import get_connection

    conn = get_connection(kb_root)
    sections_indexed = 0
    for filename in created + updated:
        stats = fingerprint_file(kb_root, wiki_dir / filename, conn, force=True)
        sections_indexed += stats["new"] + stats["updated"]
    conn.close()

    return {
        "source": source_path.name,
        "pages_created": created,
        "pages_updated": updated,
        "pages_skipped": [f"{f} (duplicate of {ex})" for f, ex in skipped],
        "sections_indexed": sections_indexed,
    }


def main():
    parser = argparse.ArgumentParser(description="Ingest a source into MindGraph")
    parser.add_argument("kb_root", help="Knowledge base root directory")
    parser.add_argument("source", help="Source file to ingest")
    parser.add_argument("--no-compile", action="store_true",
                        help="Skip Claude compilation — use fallback template (faster)")
    args = parser.parse_args()

    kb_root = Path(args.kb_root).resolve()
    source = Path(args.source).resolve()

    if not source.exists():
        print(f"Error: Source file not found: {source}")
        return

    print(f"Ingesting {source.name}{'  (no-compile mode)' if args.no_compile else ''}...")
    result = ingest_source(kb_root, source, no_compile=args.no_compile)
    print(f"Done: {len(result['pages_created'])} pages created, "
          f"{len(result['pages_updated'])} updated, "
          f"{len(result.get('pages_skipped', []))} skipped (duplicates), "
          f"{result['sections_indexed']} sections indexed")
    for p in result["pages_created"]:
        print(f"  + wiki/{p}")
    for p in result["pages_updated"]:
        print(f"  ~ wiki/{p}")
    for p in result.get("pages_skipped", []):
        print(f"  - {p}")


if __name__ == "__main__":
    main()
