"""Markdown section parser — splits .md files into sections by h2/h3 headings."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Section:
    heading: str
    heading_level: int
    line_start: int  # 1-indexed
    line_end: int  # 1-indexed, inclusive
    content: str


def parse_sections(filepath: Path) -> list[Section]:
    """Parse a markdown file into sections split on h2/h3 boundaries.

    - Content before first heading becomes a section with heading="## (preamble)"
    - Code blocks (```) are skipped even if they contain # characters
    - Sections run from heading to next same-or-higher level heading, or EOF
    """
    text = filepath.read_text(encoding="utf-8")
    lines = text.split("\n")
    sections: list[Section] = []
    current_heading = "## (preamble)"
    current_level = 2
    current_start = 1
    current_lines: list[str] = []
    in_code_block = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Track code fences
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            current_lines.append(line)
            continue

        if in_code_block:
            current_lines.append(line)
            continue

        # Check for h2 or h3 heading
        heading_level = 0
        if stripped.startswith("### ") and not stripped.startswith("#### "):
            heading_level = 3
        elif stripped.startswith("## ") and not stripped.startswith("### "):
            heading_level = 2

        if heading_level > 0:
            # Save previous section if it has content
            if current_lines or current_heading == "## (preamble)":
                content = "\n".join(current_lines)
                if content.strip():  # skip empty preambles
                    sections.append(Section(
                        heading=current_heading,
                        heading_level=current_level,
                        line_start=current_start,
                        line_end=i - 1,
                        content=content,
                    ))

            current_heading = stripped
            current_level = heading_level
            current_start = i
            current_lines = [line]
        else:
            current_lines.append(line)

    # Final section
    if current_lines:
        content = "\n".join(current_lines)
        if content.strip():
            sections.append(Section(
                heading=current_heading,
                heading_level=current_level,
                line_start=current_start,
                line_end=len(lines),
                content=content,
            ))

    return sections


def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
