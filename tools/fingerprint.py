"""Build/rebuild the SQLite fingerprint index from wiki markdown files."""
from __future__ import annotations
import argparse
import subprocess
from pathlib import Path

from tools.db import (
    delete_stale_sections,
    get_connection,
    get_metadata,
    set_metadata,
    upsert_section,
)
from tools.parser import Section, compute_content_hash, parse_sections

SKIP_FILES = {"schema.md", "index.md", "log.md"}


def call_claude_print(prompt: str) -> str:
    """Call claude --print for caveman compression. Falls back to truncation."""
    try:
        result = subprocess.run(
            ["claude", "--print", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def generate_brief(section: Section) -> str:
    """Generate a caveman-compressed 1-line summary of a section."""
    content = section.content[:2000]  # limit input size
    prompt = (
        "Compress to ONE sentence, caveman style. "
        "Drop articles, filler, pleasantries. Keep technical terms exact. "
        "No hedging. Fragment fine.\n\n"
        f"Section heading: {section.heading}\n"
        f"Content:\n{content}"
    )
    result = call_claude_print(prompt)
    if result:
        # Take only first line
        return result.split("\n")[0].strip()
    # Fallback: first 120 chars of content
    text = section.content.replace("\n", " ").strip()
    return text[:120]


def batch_generate_briefs(sections: list[Section], batch_size: int = 10) -> list[str]:
    """Generate briefs for multiple sections in a single Claude call."""
    briefs = []
    for i in range(0, len(sections), batch_size):
        batch = sections[i : i + batch_size]
        if len(batch) == 1:
            briefs.append(generate_brief(batch[0]))
            continue

        numbered = []
        for j, s in enumerate(batch, start=1):
            content = s.content[:1000]
            numbered.append(f"[{j}] Heading: {s.heading}\n{content}")

        prompt = (
            "For each numbered section below, write ONE caveman-compressed sentence summary. "
            "Drop articles, filler. Keep technical terms. "
            "Format exactly: [N] summary\n\n" + "\n\n".join(numbered)
        )
        result = call_claude_print(prompt)
        if result:
            # Parse numbered responses
            parsed = {}
            for line in result.split("\n"):
                line = line.strip()
                if line.startswith("[") and "]" in line:
                    idx_end = line.index("]")
                    try:
                        num = int(line[1:idx_end])
                        parsed[num] = line[idx_end + 1 :].strip()
                    except ValueError:
                        continue
            for j in range(1, len(batch) + 1):
                briefs.append(parsed.get(j, batch[j - 1].heading))
        else:
            for s in batch:
                briefs.append(s.heading)
    return briefs


def generate_fingerprint(section: Section) -> str:
    """Generate caveman-compressed version of the full section."""
    content = section.content[:4000]
    prompt = (
        "Compress this markdown section into caveman-speak. "
        "Drop articles, filler, pleasantries, hedging. "
        "Keep code blocks, URLs, paths, technical terms EXACTLY. "
        "Preserve heading structure.\n\n" + content
    )
    result = call_claude_print(prompt)
    return result if result else section.content[:500]


def fingerprint_file(
    kb_root: Path, wiki_file: Path, conn, force: bool = False
) -> dict:
    """Parse a single wiki file, fingerprint changed sections, update DB."""
    rel_path = str(wiki_file.relative_to(kb_root))
    sections = parse_sections(wiki_file)
    stats = {"file": rel_path, "total": len(sections), "new": 0, "updated": 0, "stale_removed": 0}

    if not sections:
        return stats

    # Check which sections need updating
    needs_update = []
    valid_hashes = set()
    for section in sections:
        h = compute_content_hash(section.content)
        valid_hashes.add(h)
        if force:
            needs_update.append((section, h))
        else:
            existing = conn.execute(
                "SELECT content_hash FROM sections WHERE file=? AND heading=? AND line_start=?",
                (rel_path, section.heading, section.line_start),
            ).fetchone()
            if not existing or existing["content_hash"] != h:
                needs_update.append((section, h))

    # Generate briefs in batch for sections that need updating
    if needs_update:
        sections_to_brief = [s for s, _ in needs_update]
        briefs = batch_generate_briefs(sections_to_brief)

        for (section, content_hash), brief in zip(needs_update, briefs):
            fp = generate_fingerprint(section)
            existing = conn.execute(
                "SELECT id FROM sections WHERE file=? AND heading=? AND line_start=?",
                (rel_path, section.heading, section.line_start),
            ).fetchone()

            upsert_section(
                conn,
                file=rel_path,
                heading=section.heading,
                heading_level=section.heading_level,
                line_start=section.line_start,
                line_end=section.line_end,
                brief=brief,
                fingerprint=fp,
                content_hash=content_hash,
            )
            if existing:
                stats["updated"] += 1
            else:
                stats["new"] += 1

    # Remove stale sections
    stats["stale_removed"] = delete_stale_sections(conn, rel_path, valid_hashes)
    return stats


def fingerprint_all(kb_root: Path, force: bool = False) -> dict:
    """Fingerprint all wiki/*.md files."""
    wiki_dir = kb_root / "wiki"
    if not wiki_dir.exists():
        return {"error": "wiki/ directory not found"}

    conn = get_connection(kb_root)
    totals = {"files_processed": 0, "sections_total": 0, "sections_new": 0,
              "sections_updated": 0, "stale_removed": 0}

    for md_file in sorted(wiki_dir.glob("**/*.md")):
        if md_file.name in SKIP_FILES:
            continue
        stats = fingerprint_file(kb_root, md_file, conn, force)
        totals["files_processed"] += 1
        totals["sections_total"] += stats["total"]
        totals["sections_new"] += stats["new"]
        totals["sections_updated"] += stats["updated"]
        totals["stale_removed"] += stats["stale_removed"]
        print(f"  {stats['file']}: {stats['total']} sections "
              f"({stats['new']} new, {stats['updated']} updated, {stats['stale_removed']} stale removed)")

    # Clean up sections for files that no longer exist
    all_files = {str(f.relative_to(kb_root)) for f in wiki_dir.glob("**/*.md") if f.name not in SKIP_FILES}
    db_files = {r["file"] for r in conn.execute("SELECT DISTINCT file FROM sections").fetchall()}
    orphan_files = db_files - all_files
    for orphan in orphan_files:
        from tools.db import delete_sections_for_file
        removed = delete_sections_for_file(conn, orphan)
        totals["stale_removed"] += removed
        print(f"  Removed {removed} orphan sections from deleted file: {orphan}")

    set_metadata(conn, "last_fingerprint", __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).isoformat())
    conn.close()
    return totals


def main():
    parser = argparse.ArgumentParser(description="Build/rebuild MindGraph fingerprint index")
    parser.add_argument("kb_root", help="Knowledge base root directory")
    parser.add_argument("--force", action="store_true", help="Re-fingerprint all sections, not just changed")
    parser.add_argument("--file", help="Fingerprint a single wiki file")
    args = parser.parse_args()

    kb_root = Path(args.kb_root).resolve()
    if args.file:
        conn = get_connection(kb_root)
        wiki_file = Path(args.file)
        if not wiki_file.is_absolute():
            wiki_file = kb_root / wiki_file
        stats = fingerprint_file(kb_root, wiki_file, conn, args.force)
        conn.close()
        print(f"Fingerprinted {stats['file']}: {stats['total']} sections "
              f"({stats['new']} new, {stats['updated']} updated)")
    else:
        print(f"Fingerprinting all wiki files in {kb_root}...")
        totals = fingerprint_all(kb_root, args.force)
        print(f"\nDone: {totals['files_processed']} files, {totals['sections_total']} sections "
              f"({totals['sections_new']} new, {totals['sections_updated']} updated, "
              f"{totals['stale_removed']} stale removed)")


if __name__ == "__main__":
    main()
