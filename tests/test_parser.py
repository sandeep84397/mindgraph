"""Tests for the markdown section parser."""
import tempfile
from pathlib import Path

import pytest

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.parser import parse_sections, compute_content_hash


@pytest.fixture
def sample_page(tmp_path):
    content = (Path(__file__).parent / "fixtures" / "sample_wiki_page.md").read_text()
    p = tmp_path / "test.md"
    p.write_text(content)
    return p


@pytest.fixture
def code_block_page(tmp_path):
    content = """# Test Page

## Section One

Some text here.

```python
## This is NOT a heading
def foo():
    ### Also not a heading
    pass
```

## Section Two

More text after code block.

### Subsection

Details here.
"""
    p = tmp_path / "code_test.md"
    p.write_text(content)
    return p


@pytest.fixture
def preamble_page(tmp_path):
    content = """This is preamble text before any heading.
It should become its own section.

## First Real Section

Content here.
"""
    p = tmp_path / "preamble.md"
    p.write_text(content)
    return p


class TestParseSections:
    def test_basic_parsing(self, sample_page):
        sections = parse_sections(sample_page)
        # Should have: preamble (# title), Summary, Details (with subsections), References, See Also
        assert len(sections) >= 4
        headings = [s.heading for s in sections]
        assert "## Summary" in headings
        assert "## Details" in headings or any("Details" in h for h in headings)

    def test_heading_levels(self, sample_page):
        sections = parse_sections(sample_page)
        for s in sections:
            assert s.heading_level in (2, 3)

    def test_line_numbers(self, sample_page):
        sections = parse_sections(sample_page)
        for s in sections:
            assert s.line_start >= 1
            assert s.line_end >= s.line_start

    def test_no_overlap(self, sample_page):
        sections = parse_sections(sample_page)
        for i in range(len(sections) - 1):
            assert sections[i].line_end < sections[i + 1].line_start or \
                   sections[i].line_end == sections[i + 1].line_start - 1

    def test_code_blocks_not_split(self, code_block_page):
        sections = parse_sections(code_block_page)
        headings = [s.heading for s in sections]
        # The ## inside code block should NOT create a section
        assert "## This is NOT a heading" not in headings
        # But real headings should be found
        assert "## Section One" in headings
        assert "## Section Two" in headings

    def test_h3_subsections(self, code_block_page):
        sections = parse_sections(code_block_page)
        headings = [s.heading for s in sections]
        assert "### Subsection" in headings

    def test_preamble(self, preamble_page):
        sections = parse_sections(preamble_page)
        assert len(sections) >= 2
        assert sections[0].heading == "## (preamble)"
        assert "preamble text" in sections[0].content

    def test_content_preserved(self, sample_page):
        sections = parse_sections(sample_page)
        all_content = "\n".join(s.content for s in sections)
        assert "self_attention" in all_content
        assert "softmax" in all_content

    def test_empty_file(self, tmp_path):
        p = tmp_path / "empty.md"
        p.write_text("")
        sections = parse_sections(p)
        assert sections == []


class TestContentHash:
    def test_deterministic(self):
        h1 = compute_content_hash("hello world")
        h2 = compute_content_hash("hello world")
        assert h1 == h2

    def test_different_content(self):
        h1 = compute_content_hash("hello")
        h2 = compute_content_hash("world")
        assert h1 != h2

    def test_sha256_length(self):
        h = compute_content_hash("test")
        assert len(h) == 64  # SHA-256 hex digest
