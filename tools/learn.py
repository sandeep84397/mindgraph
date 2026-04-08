"""Learn on miss — when a search finds nothing, scan the codebase and create a wiki page.

Pipeline:
  1. Quality gate:    instant stop-word check — reject junk before any LLM call.
  2. Caveman refine:  compress query via caveman to extract only meaningful terms.
  3. Dedup:           fuzzy-match refined slug against existing wiki pages + FTS.
  4. Grep:            search codebase using refined terms (more precise hits).
  5. Fast stub:       build wiki page from grep results instantly (no LLM).
  6. Background:      enrich with claude --print fingerprints async.
"""
from __future__ import annotations
import re
import subprocess
import threading
from difflib import SequenceMatcher
from pathlib import Path

from tools.db import get_connection, get_all_sections, search_fts, upsert_section
from tools.ingest import append_log, slugify, update_index
from tools.parser import parse_sections, compute_content_hash

# ── Quality gate ────────────────────────────────────────────────────
MIN_MATCHES = 3          # grep must hit this many files to proceed
MIN_QUERY_LEN = 3        # reject single/two-char queries
MAX_QUERY_WORDS = 15     # relaxed — caveman handles distillation downstream

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must", "it", "its",
    "this", "that", "these", "those", "i", "me", "my", "we", "our", "you",
    "your", "he", "she", "they", "them", "what", "which", "who", "whom",
    "how", "where", "when", "why", "all", "each", "every", "both", "few",
    "more", "most", "some", "any", "no", "not", "only", "same", "so",
    "than", "too", "very", "just", "about", "above", "after", "before",
    "between", "into", "through", "during", "for", "with", "at", "by",
    "from", "of", "on", "to", "in", "out", "up", "down", "off", "over",
    "under", "again", "then", "once", "here", "there", "and", "but", "or",
    "nor", "if", "stuff", "things", "thing", "something", "anything",
}

# File extensions to grep (mirrors watch.py's _should_handle)
CODE_EXTS = (
    "py", "js", "ts", "tsx", "jsx", "go", "rs", "java", "c", "cpp", "h",
    "rb", "swift", "kt", "cs", "sh", "md", "txt", "yaml", "yml", "json",
    "toml",
)

# ── Dedup ───────────────────────────────────────────────────────────
SLUG_SIMILARITY_THRESHOLD = 0.7   # SequenceMatcher ratio


def _meaningful_words(query: str) -> list[str]:
    """Extract non-stop-word tokens from query."""
    words = re.findall(r"[a-zA-Z_]\w*", query.lower())
    return [w for w in words if w not in STOP_WORDS and len(w) >= 2]


def passes_quality_gate(query: str) -> tuple[bool, str]:
    """Check if a query is specific enough to warrant a wiki page.

    Returns (passed, reason).
    """
    stripped = query.strip()
    if len(stripped) < MIN_QUERY_LEN:
        return False, "query too short"

    words = stripped.split()
    if len(words) > MAX_QUERY_WORDS:
        return False, "query too long — use specific terms"

    meaningful = _meaningful_words(stripped)
    if not meaningful:
        return False, "query contains only stop words"

    return True, ""


def caveman_refine(query: str) -> str:
    """Run query through caveman compression to extract only meaningful terms.

    Called AFTER the quality gate passes. Returns the distilled search key.
    Falls back to stop-word filtering if claude is unavailable.
    """
    prompt = (
        "Extract ONLY the technical search terms from this query. "
        "Drop all filler, stop words, questions, pleasantries. "
        "Return ONLY the key terms separated by spaces. Nothing else.\n\n"
        f"Query: {query}"
    )
    try:
        result = subprocess.run(
            ["claude", "--print", "-p", prompt],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            refined = result.stdout.strip().split("\n")[0].strip()
            # Sanity check: caveman should return fewer or equal words
            refined_words = re.findall(r"[a-zA-Z_]\w*", refined)
            if refined_words:
                return " ".join(refined_words)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # Fallback: stop-word filter
    return " ".join(_meaningful_words(query))


def grep_codebase(kb_root: Path, refined_terms: str) -> list[dict]:
    """Grep the codebase for refined terms. Returns list of {file, line, text} dicts.

    Uses the caveman-refined terms OR'd together via ripgrep.
    Falls back to plain grep if rg is unavailable.
    """
    words = re.findall(r"[a-zA-Z_]\w*", refined_terms.lower())
    if not words:
        return []

    # Build a regex pattern: word1|word2|word3
    pattern = "|".join(re.escape(w) for w in words)

    # Glob for code extensions
    globs = [f"*.{ext}" for ext in CODE_EXTS]

    matches = []
    try:
        glob_args = []
        for g in globs:
            glob_args += ["--glob", g]

        result = subprocess.run(
            ["rg", "--no-heading", "-n", "-i", "--max-count", "3",
             "--max-filesize", "100K"] + glob_args + [pattern, str(kb_root)],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            # format: file:line:text
            parts = line.split(":", 2)
            if len(parts) >= 3:
                matches.append({
                    "file": parts[0],
                    "line": int(parts[1]) if parts[1].isdigit() else 0,
                    "text": parts[2].strip(),
                })
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Fallback: use grep
        try:
            result = subprocess.run(
                ["grep", "-r", "-n", "-i", "--include=*.py", "--include=*.md",
                 "-E", pattern, str(kb_root)],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    matches.append({
                        "file": parts[0],
                        "line": int(parts[1]) if parts[1].isdigit() else 0,
                        "text": parts[2].strip(),
                    })
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return matches


def has_duplicate(kb_root: Path, query: str) -> bool:
    """Check if a wiki page for this query already exists.

    Two checks:
      1. Slug similarity against existing wiki filenames.
      2. FTS search for the query terms (relaxed — any partial match counts).
    """
    slug = slugify(query)
    wiki_dir = kb_root / "wiki"

    # 1. Check slug similarity against existing pages
    for page in wiki_dir.glob("*.md"):
        if page.name in ("schema.md", "index.md", "log.md"):
            continue
        existing_slug = page.stem
        ratio = SequenceMatcher(None, slug, existing_slug).ratio()
        if ratio >= SLUG_SIMILARITY_THRESHOLD:
            return True

    # 2. Check FTS — require ALL refined terms to match (AND), not just any (OR).
    #    This prevents common terms like "sections" from triggering false dedup.
    conn = get_connection(kb_root)
    meaningful = _meaningful_words(query)
    if meaningful:
        # FTS AND query — all terms must be present in a single section
        fts_query = " AND ".join(meaningful)
        try:
            results = search_fts(conn, fts_query, limit=3)
            if len(results) >= 3:
                conn.close()
                return True
        except Exception:
            pass
    conn.close()
    return False


def build_stub_page(query: str, refined_terms: str, grep_hits: list[dict], kb_root: Path) -> str:
    """Build a wiki page from grep results — no LLM call, instant."""
    words = re.findall(r"[a-zA-Z_]\w*", refined_terms)
    title = " ".join(w.title() for w in words) if words else query.title()

    # Group hits by file
    by_file: dict[str, list[dict]] = {}
    for hit in grep_hits[:30]:  # cap at 30 hits
        fname = hit["file"]
        try:
            rel = str(Path(fname).relative_to(kb_root))
        except ValueError:
            rel = fname
        by_file.setdefault(rel, []).append(hit)

    sections = [f"# {title}\n"]
    sections.append(f"## Summary\n")
    sections.append(
        f"Auto-learned from {len(by_file)} file(s) matching: `{query}`\n"
    )
    sections.append("## Details\n")

    for rel_file, hits in sorted(by_file.items()):
        sections.append(f"### {rel_file}\n")
        for h in hits[:5]:
            sections.append(f"- L{h['line']}: `{h['text'][:120]}`")
        sections.append("")

    sections.append(f"\n## References\n")
    for rel_file in sorted(by_file.keys()):
        sections.append(f"- `{rel_file}`")

    sections.append(f"\n## See Also\n")
    sections.append("<!-- Cross-references will be added as the graph grows -->\n")

    return "\n".join(sections)


def enrich_in_background(kb_root: Path, wiki_path: Path) -> None:
    """Re-fingerprint a wiki page with full claude --print briefs in a thread."""
    def _enrich():
        try:
            from tools.fingerprint import fingerprint_file
            conn = get_connection(kb_root)
            fingerprint_file(kb_root, wiki_path, conn, force=True)
            conn.close()
        except Exception:
            pass  # best-effort background enrichment

    thread = threading.Thread(target=_enrich, daemon=True)
    thread.start()


def learn(kb_root: Path, query: str) -> dict:
    """Learn from a search miss: scan codebase, create wiki page, index it.

    Returns:
      {"learned": True, "page": "...", "sections": N, "reason": "..."}
      or {"learned": False, "reason": "..."}
    """
    # ── Quality gate (instant, no LLM) ────────────────────
    passed, reason = passes_quality_gate(query)
    if not passed:
        return {"learned": False, "reason": reason}

    # ── Caveman refine (distill to key terms) ────────────
    refined = caveman_refine(query)
    if not refined:
        return {"learned": False, "reason": "no meaningful terms after refinement"}

    # ── Dedup (uses refined terms for slug) ──────────────
    if has_duplicate(kb_root, refined):
        return {"learned": False, "reason": "similar wiki page already exists"}

    # ── Grep codebase (uses refined terms) ───────────────
    grep_hits = grep_codebase(kb_root, refined)
    hit_files = {h["file"] for h in grep_hits}
    if len(hit_files) < MIN_MATCHES:
        return {
            "learned": False,
            "reason": f"only {len(hit_files)} file(s) matched (need {MIN_MATCHES}+)",
        }

    # ── Fast stub ────────────────────────────────────────
    slug = slugify(refined)
    wiki_dir = kb_root / "wiki"
    wiki_dir.mkdir(exist_ok=True)
    wiki_path = wiki_dir / f"{slug}.md"

    content = build_stub_page(query, refined, grep_hits, kb_root)
    wiki_path.write_text(content, encoding="utf-8")

    # ── Instant index (no LLM) ───────────────────────────
    conn = get_connection(kb_root)
    sections = parse_sections(wiki_path)
    rel_path = str(wiki_path.relative_to(kb_root))
    indexed = 0
    for section in sections:
        content_hash = compute_content_hash(section.content)
        # Use heading as brief (instant, no LLM)
        brief = section.heading.lstrip("# ").strip()
        if not brief or brief == "(preamble)":
            brief = f"Auto-learned: {refined}"
        upsert_section(
            conn,
            file=rel_path,
            heading=section.heading,
            heading_level=section.heading_level,
            line_start=section.line_start,
            line_end=section.line_end,
            brief=brief,
            fingerprint=section.content[:500],
            content_hash=content_hash,
        )
        indexed += 1
    conn.close()

    # ── Log it ───────────────────────────────────────────
    update_index(kb_root, [f"{slug}.md"])
    append_log(kb_root, "LEARN", f"Auto-learned '{query}' (refined: '{refined}') → wiki/{slug}.md ({indexed} sections)")

    # ── Enrich in background ─────────────────────────────
    enrich_in_background(kb_root, wiki_path)

    return {
        "learned": True,
        "page": f"wiki/{slug}.md",
        "sections": indexed,
        "files_matched": len(hit_files),
        "refined_terms": refined,
        "reason": "created from codebase scan",
    }


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Learn a topic from codebase (manual trigger)")
    parser.add_argument("kb_root", help="Knowledge base root directory")
    parser.add_argument("query", help="Topic to learn about")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    kb_root = Path(args.kb_root).resolve()
    result = learn(kb_root, args.query)

    if args.json:
        print(json.dumps(result, indent=2))
    elif result.get("learned"):
        print(f"Learned: {result['page']} ({result['sections']} sections from {result['files_matched']} files)")
    else:
        print(f"Skipped: {result['reason']}")


if __name__ == "__main__":
    main()
