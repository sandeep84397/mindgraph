"""Lint the MindGraph knowledge base — detect stale fingerprints, orphans, broken links."""
from __future__ import annotations
import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

from tools.db import delete_sections_for_file, get_connection, get_all_sections
from tools.parser import compute_content_hash, parse_sections

SKIP_FILES = {"schema.md", "index.md", "log.md"}


@dataclass
class LintIssue:
    severity: str  # "error" | "warning" | "info"
    category: str  # "stale" | "orphan" | "broken_link" | "missing_index" | "empty"
    file: str
    line: Optional[int]
    message: str


def lint_staleness(kb_root: Path, conn) -> list[LintIssue]:
    """Check for sections where wiki content changed but fingerprint wasn't updated."""
    issues = []
    wiki_dir = kb_root / "wiki"
    for md_file in sorted(wiki_dir.glob("**/*.md")):
        if md_file.name in SKIP_FILES:
            continue
        rel_path = str(md_file.relative_to(kb_root))
        sections = parse_sections(md_file)
        db_sections = get_all_sections(conn, rel_path)
        db_hashes = {r["content_hash"] for r in db_sections}

        for section in sections:
            h = compute_content_hash(section.content)
            if h not in db_hashes:
                issues.append(LintIssue(
                    severity="warning",
                    category="stale",
                    file=rel_path,
                    line=section.line_start,
                    message=f"Section '{section.heading}' content changed but fingerprint not updated",
                ))
    return issues


def lint_orphan_db_entries(kb_root: Path, conn) -> list[LintIssue]:
    """Find DB entries whose source files no longer exist."""
    issues = []
    wiki_dir = kb_root / "wiki"
    all_files = {str(f.relative_to(kb_root)) for f in wiki_dir.glob("**/*.md") if f.name not in SKIP_FILES}
    db_files = {r["file"] for r in conn.execute("SELECT DISTINCT file FROM sections").fetchall()}

    for orphan in db_files - all_files:
        issues.append(LintIssue(
            severity="error",
            category="orphan",
            file=orphan,
            line=None,
            message=f"DB has sections for deleted file: {orphan}",
        ))
    return issues


def lint_broken_links(kb_root: Path) -> list[LintIssue]:
    """Check [[Page Name]] cross-references point to existing files."""
    issues = []
    wiki_dir = kb_root / "wiki"
    link_pattern = re.compile(r"\[\[(.+?)\]\]")

    for md_file in sorted(wiki_dir.glob("**/*.md")):
        if md_file.name in SKIP_FILES:
            continue
        content = md_file.read_text(encoding="utf-8")
        rel_path = str(md_file.relative_to(kb_root))

        for i, line in enumerate(content.split("\n"), 1):
            for match in link_pattern.finditer(line):
                page_name = match.group(1)
                slug = page_name.lower().replace(" ", "_")
                target = wiki_dir / f"{slug}.md"
                if not target.exists():
                    issues.append(LintIssue(
                        severity="warning",
                        category="broken_link",
                        file=rel_path,
                        line=i,
                        message=f"Broken link [[{page_name}]] — wiki/{slug}.md not found",
                    ))
    return issues


def lint_missing_index(kb_root: Path) -> list[LintIssue]:
    """Find wiki pages not listed in index.md."""
    issues = []
    wiki_dir = kb_root / "wiki"
    index_path = wiki_dir / "index.md"
    if not index_path.exists():
        return issues

    index_content = index_path.read_text(encoding="utf-8").lower()

    for md_file in sorted(wiki_dir.glob("**/*.md")):
        if md_file.name in SKIP_FILES:
            continue
        page_name = md_file.stem.replace("_", " ")
        if page_name not in index_content and md_file.stem not in index_content:
            issues.append(LintIssue(
                severity="info",
                category="missing_index",
                file=str(md_file.relative_to(kb_root)),
                line=None,
                message=f"Page not listed in index.md",
            ))
    return issues


def lint_empty_sections(kb_root: Path) -> list[LintIssue]:
    """Find sections with no content beyond the heading."""
    issues = []
    wiki_dir = kb_root / "wiki"
    for md_file in sorted(wiki_dir.glob("**/*.md")):
        if md_file.name in SKIP_FILES:
            continue
        rel_path = str(md_file.relative_to(kb_root))
        sections = parse_sections(md_file)
        for section in sections:
            # Remove heading line, check if rest is empty
            lines = section.content.split("\n")
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
            if not body:
                issues.append(LintIssue(
                    severity="info",
                    category="empty",
                    file=rel_path,
                    line=section.line_start,
                    message=f"Empty section: {section.heading}",
                ))
    return issues


def lint_knowledge_base(kb_root: Path) -> list[LintIssue]:
    """Run all lint checks."""
    conn = get_connection(kb_root)
    issues = []
    issues.extend(lint_staleness(kb_root, conn))
    issues.extend(lint_orphan_db_entries(kb_root, conn))
    issues.extend(lint_broken_links(kb_root))
    issues.extend(lint_missing_index(kb_root))
    issues.extend(lint_empty_sections(kb_root))
    conn.close()
    return issues


def fix_issues(kb_root: Path, issues: list[LintIssue]) -> int:
    """Auto-fix what we can: re-fingerprint stale, remove orphans."""
    fixed = 0
    conn = get_connection(kb_root)

    stale_files = {i.file for i in issues if i.category == "stale"}
    if stale_files:
        from tools.fingerprint import fingerprint_file
        for f in stale_files:
            filepath = kb_root / f
            if filepath.exists():
                fingerprint_file(kb_root, filepath, conn, force=True)
                fixed += 1

    orphan_files = {i.file for i in issues if i.category == "orphan"}
    for f in orphan_files:
        delete_sections_for_file(conn, f)
        fixed += 1

    conn.close()
    return fixed


def format_report(issues: list[LintIssue]) -> str:
    """Format lint issues for display."""
    if not issues:
        return "No issues found. Knowledge base is healthy."

    lines = []
    by_severity = {"error": [], "warning": [], "info": []}
    for issue in issues:
        by_severity[issue.severity].append(issue)

    for severity in ["error", "warning", "info"]:
        group = by_severity[severity]
        if group:
            lines.append(f"\n{severity.upper()} ({len(group)}):")
            for issue in group:
                loc = f"{issue.file}:{issue.line}" if issue.line else issue.file
                lines.append(f"  [{issue.category}] {loc} — {issue.message}")

    lines.append(f"\nTotal: {len(issues)} issues "
                 f"({len(by_severity['error'])} errors, "
                 f"{len(by_severity['warning'])} warnings, "
                 f"{len(by_severity['info'])} info)")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Lint MindGraph knowledge base")
    parser.add_argument("kb_root", help="Knowledge base root directory")
    parser.add_argument("--fix", action="store_true", help="Auto-fix stale fingerprints and orphans")
    args = parser.parse_args()

    kb_root = Path(args.kb_root).resolve()
    print(f"Linting {kb_root}...")

    issues = lint_knowledge_base(kb_root)
    print(format_report(issues))

    if args.fix and issues:
        fixable = [i for i in issues if i.category in ("stale", "orphan")]
        if fixable:
            print(f"\nFixing {len(fixable)} auto-fixable issues...")
            fixed = fix_issues(kb_root, issues)
            print(f"Fixed {fixed} issues.")


if __name__ == "__main__":
    main()
