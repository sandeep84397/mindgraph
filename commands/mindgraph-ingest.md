---
description: "Ingest a source document into the MindGraph knowledge base"
---

Use the mindgraph skill to ingest a source. The user should provide the source file path.

Run: `python3 -m tools ingest <kb_root> <source_file>`

This will: copy to raw/, compile wiki pages, update index/log, and fingerprint new sections.
