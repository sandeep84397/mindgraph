# Wiki Schema

## Page Types

- **Entity page**: A single concept, person, algorithm, or artifact. Filename: `snake_case.md`
- **Topic page**: A broad area linking multiple entities. Filename: `topic_snake_case.md`
- **Summary page**: A synthesis of a specific source. Filename: `summary_snake_case.md`

## Required Sections

Every wiki page must include these sections:

- `## Summary` — 2-3 sentence overview of the page's subject
- `## Details` — Main content, use h3 subsections for structure
- `## References` — Links to raw/ sources and external URLs
- `## See Also` — Cross-references to related wiki pages using `[[Page Name]]` format

## Cross-Reference Format

Use `[[Page Name]]` to link to other wiki pages. The referenced file is `wiki/page_name.md` (snake_case of the page name).

## Rules

- One concept per entity page
- Cite sources from `raw/` using relative paths
- No duplicate pages for the same concept — update existing pages instead
- Update `index.md` when creating new pages
- Log all changes to `log.md` with format: `[YYYY-MM-DD HH:MM] [ACTION] description`
- Use h2 (`##`) for main sections, h3 (`###`) for subsections
- Keep summaries concise — details go in the Details section
