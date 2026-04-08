"""Search the MindGraph fingerprint index via FTS5."""
from __future__ import annotations
import argparse
from pathlib import Path

from tools.db import get_connection, get_stats, search_fts
from tools.stats import record_search
from tools.learn import learn


def is_disabled(kb_root: Path) -> bool:
    """Check if MindGraph search is disabled via metadata toggle."""
    conn = get_connection(kb_root)
    val = conn.execute(
        "SELECT value FROM metadata WHERE key = 'search_disabled'", ()
    ).fetchone()
    conn.close()
    return val is not None and val["value"] == "true"


def set_disabled(kb_root: Path, disabled: bool) -> None:
    """Enable or disable MindGraph search."""
    from tools.db import set_metadata
    conn = get_connection(kb_root)
    set_metadata(conn, "search_disabled", "true" if disabled else "false")
    conn.close()


def search(kb_root: Path, query: str, limit: int = 20, no_learn: bool = False) -> list[dict]:
    """Search the fingerprint index. Returns matched sections with file pointers.

    On zero results, triggers learn-on-miss unless no_learn is True or
    search is globally disabled.
    """
    if is_disabled(kb_root):
        return []

    conn = get_connection(kb_root)
    results = search_fts(conn, query, limit)
    conn.close()

    if not results and not no_learn:
        outcome = learn(kb_root, query)
        if outcome.get("learned"):
            # Re-search to pick up the just-indexed sections
            conn = get_connection(kb_root)
            results = search_fts(conn, query, limit)
            conn.close()

    if results:
        record_search(kb_root, len(results))
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
    parser.add_argument("query", nargs="?", default="", help="Search query")
    parser.add_argument("--limit", type=int, default=20, help="Max results")
    parser.add_argument("--verbose", action="store_true", help="Show fingerprint text")
    parser.add_argument("--stats", action="store_true", help="Show index stats")
    parser.add_argument("--no-learn", action="store_true", help="Skip learn-on-miss for this query")
    parser.add_argument("--disable", action="store_true", help="Disable MindGraph search globally")
    parser.add_argument("--enable", action="store_true", help="Re-enable MindGraph search")
    args = parser.parse_args()

    kb_root = Path(args.kb_root).resolve()

    if args.disable:
        set_disabled(kb_root, True)
        print("MindGraph search disabled. Use --enable to re-enable.")
        return

    if args.enable:
        set_disabled(kb_root, False)
        print("MindGraph search re-enabled.")
        return

    if is_disabled(kb_root):
        print("MindGraph search is disabled. Use --enable to re-enable.")
        return

    if not args.query and not args.stats:
        parser.error("query is required (unless using --stats, --disable, or --enable)")

    if args.stats:
        conn = get_connection(kb_root)
        s = get_stats(conn)
        conn.close()
        print(f"Index: {s['total_sections']} sections across {s['total_files']} files")
        return

    conn = get_connection(kb_root)
    direct_results = search_fts(conn, args.query, args.limit)
    conn.close()

    if direct_results:
        record_search(kb_root, len(direct_results))
        print(f"Found {len(direct_results)} results for \"{args.query}\":\n")
        print(format_results(direct_results, args.verbose))
    elif args.no_learn:
        print(f"No results for \"{args.query}\" (learn-on-miss skipped)")
    else:
        outcome = learn(kb_root, args.query)
        if outcome.get("learned"):
            print(f"No existing results — learned from codebase:")
            print(f"  + {outcome['page']} ({outcome['sections']} sections from {outcome['files_matched']} files)\n")
            conn = get_connection(kb_root)
            results = search_fts(conn, args.query, args.limit)
            conn.close()
            if results:
                record_search(kb_root, len(results))
                print(format_results(results, args.verbose))
        else:
            print(f"No results for \"{args.query}\" — {outcome.get('reason', 'unknown')}")


if __name__ == "__main__":
    main()
