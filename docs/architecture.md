# MindGraph Architecture

## System Overview

```mermaid
graph TB
    subgraph "Layer 1: Wiki (Karpathy Pattern)"
        RAW[raw/ — Immutable Sources]
        WIKI[wiki/ — Compiled Articles]
        SCHEMA[schema.md — Rules]
        INDEX[index.md — TOC]
        LOG[log.md — Audit Trail]
    end

    subgraph "Layer 2: Compression (Caveman)"
        CAVE[caveman-compress<br>via claude --print]
    end

    subgraph "Layer 3: Fingerprint Index"
        PARSER[parser.py<br>Split md → sections]
        HASH[SHA-256<br>Content hash]
        BRIEF[Caveman brief<br>1-line summary]
        FP[Caveman fingerprint<br>Compressed section]
        DB[(SQLite + FTS5<br>mindgraph.db)]
    end

    subgraph "Layer 4: Orchestration"
        SKILL[SKILL.md Protocol]
        CLI[CLI Tools]
        HOOKS[Claude Code Hooks]
    end

    subgraph "Layer 5: Reactive Watcher"
        WATCH[watchdog daemon]
        DEBOUNCE[2s debounce queue]
        AUTONODE[auto_node.py]
    end

    RAW -->|ingest| WIKI
    WIKI --> PARSER
    PARSER --> HASH
    HASH -->|changed?| CAVE
    CAVE --> BRIEF
    CAVE --> FP
    BRIEF --> DB
    FP --> DB

    SKILL --> CLI
    CLI --> DB
    HOOKS -->|PostToolUse| CLI

    WATCH -->|file events| DEBOUNCE
    DEBOUNCE -->|modify| PARSER
    DEBOUNCE -->|create| AUTONODE
    AUTONODE --> WIKI
```

## Search Flow

```mermaid
sequenceDiagram
    participant U as Claude Session
    participant S as search.py
    participant DB as SQLite FTS5
    participant F as Wiki File

    U->>S: python3 -m tools search . "JWT auth"
    S->>DB: SELECT ... FROM sections_fts WHERE MATCH 'JWT auth'
    DB-->>S: [{file: wiki/auth.md, lines: 12-34, brief: "JWT middleware validate..."}]
    S-->>U: auth.md:L12-L34 — JWT middleware validate token, reject expired
    U->>F: Read wiki/auth.md lines 12-34
    F-->>U: (only the relevant section content)
    Note over U: Synthesize answer from<br>targeted section reads
```

## Fingerprint Update Flow

```mermaid
sequenceDiagram
    participant W as Watcher
    participant P as parser.py
    participant DB as SQLite
    participant C as Claude CLI

    W->>W: File change detected (2s debounce)
    W->>P: parse_sections(changed_file.md)
    P-->>W: [Section1, Section2, Section3]
    
    loop For each section
        W->>DB: Check content_hash
        alt Hash unchanged
            W->>W: Skip (no API call)
        else Hash changed
            W->>C: claude --print (caveman compress)
            C-->>W: brief + fingerprint
            W->>DB: UPSERT section
        end
    end
```

## Auto-Create Node Flow

```mermaid
sequenceDiagram
    participant W as Watcher
    participant AN as auto_node.py
    participant C as Claude CLI
    participant WIKI as wiki/
    participant DB as SQLite

    W->>W: New file detected
    W->>AN: auto_create_node(new_file.py)
    AN->>AN: detect_file_type() → "code"
    AN->>C: claude --print (generate wiki page)
    C-->>AN: Wiki page content
    AN->>WIKI: Write wiki/new_file.md
    AN->>WIKI: Update index.md
    AN->>WIKI: Append to log.md
    AN->>DB: Fingerprint new page sections
```

## SQLite Schema

```mermaid
erDiagram
    sections {
        int id PK
        text file
        text heading
        int heading_level
        int line_start
        int line_end
        text brief
        text fingerprint
        text content_hash
        text updated_at
    }
    
    sections_fts {
        text brief
        text fingerprint
    }
    
    metadata {
        text key PK
        text value
    }
    
    sections ||--|| sections_fts : "FTS5 content sync"
```

## Concurrency Model

```mermaid
graph LR
    subgraph "Concurrent Access (WAL mode)"
        A[Session A<br>Writing] -->|WAL| DB[(mindgraph.db)]
        B[Session B<br>Reading] -->|WAL| DB
        C[Watcher<br>Updating] -->|WAL| DB
    end
```

SQLite WAL (Write-Ahead Logging) mode allows:
- Multiple concurrent readers
- Single writer (with readers not blocked)
- Watcher daemon and Claude sessions coexist safely
