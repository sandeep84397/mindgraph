"""Search the MindGraph fingerprint index via FTS5."""
from __future__ import annotations
import argparse
from pathlib import Path

from tools.db import get_connection, get_stats, search_fts


def search(kb_root: Path, query: str, limit: int = 20) -> list[dict]:
    """Search the fingerprint index. Returns matched sections with file pointers."""
    conn = get_connection(kb_root)
    results = search_fts(conn, query, limit)
    conn.close()
    return results


def format_results(results: list[dict], verbose: bool = False) -> str:
    """Format search results for display."""
    if not results:
        return "No results found."

    lines = []
    for i, r in enumerate(results, 1):
        loc = f"{r['file']}:L{r['line_start']}-L{r['line_end']}"
        lines.append(f"  {i}. {loc}")
        lines.append(f"     {r['heading']} — {r['brief']}")
        if verbose and r.get("fingerprint"):
            lines.append(f"     Fingerprint: {r['fingerprint'][:200]}...")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Search MindGraph knowledge base")
    parser.add_argument("kb_root", help="Knowledge base root directory")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument("--verbose", action="store_true", help="Show fingerprint text")
    parser.add_argument("--stats", action="store_true", help="Show index stats")
    args = parser.parse_args()

    kb_root = Path(args.kb_root).resolve()

    if args.stats:
        conn = get_connection(kb_root)
        s = get_stats(conn)
        conn.close()
        print(f"Index: {s['total_sections']} sections across {s['total_files']} files")
        return

    results = search(kb_root, args.query, args.limit)
    print(f"Found {len(results)} results for \"{args.query}\":\n")
    print(format_results(results, args.verbose))


if __name__ == "__main__":
    main()
