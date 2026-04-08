"""Token savings statistics — shows how many tokens MindGraph saves vs reading full files."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from tools.db import get_connection, get_all_sections, get_stats, get_metadata, set_metadata

# Rough approximation: 1 token ≈ 4 characters for English text
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate token count from character length."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def compute_savings(kb_root: Path) -> dict:
    """Calculate token savings from using the fingerprint index vs reading full files.

    Compares:
      - Full file tokens: what Claude would read without MindGraph (entire files)
      - Section tokens: what Claude actually reads (only matched line ranges)
      - Brief tokens: what the search index returns (compressed summaries)
    """
    conn = get_connection(kb_root)
    sections = get_all_sections(conn)
    db_stats = get_stats(conn)

    if not sections:
        conn.close()
        return {
            "total_files": 0,
            "total_sections": 0,
            "full_file_tokens": 0,
            "section_tokens": 0,
            "brief_tokens": 0,
            "tokens_saved_per_search": 0,
            "compression_ratio": 0,
            "cumulative_searches": 0,
            "cumulative_tokens_saved": 0,
        }

    # Gather unique files and their sizes
    file_tokens = {}
    for sec in sections:
        fpath = kb_root / sec["file"]
        if sec["file"] not in file_tokens and fpath.exists():
            file_tokens[sec["file"]] = estimate_tokens(fpath.read_text(encoding="utf-8"))

    full_file_tokens = sum(file_tokens.values())

    # Section-level tokens (what you'd read with targeted line ranges)
    section_tokens = 0
    brief_tokens = 0
    for sec in sections:
        content_len = (sec["line_end"] - sec["line_start"] + 1) * 40  # rough avg line length
        section_tokens += estimate_tokens("x" * content_len)
        brief_tokens += estimate_tokens(sec.get("brief") or "")

    # Average savings per search: reading a brief + section vs reading the whole file
    avg_file_tokens = full_file_tokens // max(len(file_tokens), 1)
    avg_section_tokens = section_tokens // max(len(sections), 1)
    avg_brief_tokens = brief_tokens // max(len(sections), 1)
    tokens_saved_per_search = avg_file_tokens - (avg_section_tokens + avg_brief_tokens)

    # Cumulative tracking
    cumulative_searches = int(get_metadata(conn, "cumulative_searches") or "0")
    cumulative_tokens_saved = int(get_metadata(conn, "cumulative_tokens_saved") or "0")

    compression_ratio = round(full_file_tokens / max(brief_tokens, 1), 1)

    conn.close()

    return {
        "total_files": db_stats["total_files"],
        "total_sections": db_stats["total_sections"],
        "full_file_tokens": full_file_tokens,
        "section_tokens": section_tokens,
        "brief_tokens": brief_tokens,
        "avg_file_tokens": avg_file_tokens,
        "avg_section_tokens": avg_section_tokens,
        "tokens_saved_per_search": max(tokens_saved_per_search, 0),
        "compression_ratio": compression_ratio,
        "cumulative_searches": cumulative_searches,
        "cumulative_tokens_saved": cumulative_tokens_saved,
    }


def record_search(kb_root: Path, sections_returned: int) -> None:
    """Call after each search to track cumulative savings."""
    conn = get_connection(kb_root)
    sections = get_all_sections(conn)
    file_tokens = {}
    for sec in sections:
        fpath = kb_root / sec["file"]
        if sec["file"] not in file_tokens and fpath.exists():
            file_tokens[sec["file"]] = estimate_tokens(fpath.read_text(encoding="utf-8"))

    avg_file_tokens = sum(file_tokens.values()) // max(len(file_tokens), 1)
    avg_section_tokens = 0
    if sections:
        total_sec_tokens = sum(
            (s["line_end"] - s["line_start"] + 1) * 10 for s in sections
        )
        avg_section_tokens = total_sec_tokens // len(sections)

    saved = max((avg_file_tokens - avg_section_tokens) * sections_returned, 0)

    prev_searches = int(get_metadata(conn, "cumulative_searches") or "0")
    prev_saved = int(get_metadata(conn, "cumulative_tokens_saved") or "0")
    set_metadata(conn, "cumulative_searches", str(prev_searches + 1))
    set_metadata(conn, "cumulative_tokens_saved", str(prev_saved + saved))
    conn.close()


def format_stats(stats: dict) -> str:
    """Format stats for terminal display."""
    lines = [
        "MindGraph Token Savings",
        "=" * 40,
        "",
        f"  Indexed files:       {stats['total_files']}",
        f"  Indexed sections:    {stats['total_sections']}",
        "",
        "  Corpus size (est. tokens):",
        f"    Full files:        {stats['full_file_tokens']:,}",
        f"    All sections:      {stats['section_tokens']:,}",
        f"    Index briefs:      {stats['brief_tokens']:,}",
        "",
        f"  Compression ratio:   {stats['compression_ratio']}x",
        f"  Saved per search:    ~{stats['tokens_saved_per_search']:,} tokens",
        "",
        "  Cumulative usage:",
        f"    Total searches:    {stats['cumulative_searches']}",
        f"    Total saved:       ~{stats['cumulative_tokens_saved']:,} tokens",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Show MindGraph token savings stats")
    parser.add_argument("kb_root", help="Knowledge base root directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    kb_root = Path(args.kb_root).resolve()
    stats = compute_savings(kb_root)

    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        print(format_stats(stats))


if __name__ == "__main__":
    main()
