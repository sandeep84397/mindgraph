Created `wiki/watch.md` with full coverage of:

- **`MindGraphHandler`** — event callbacks, filtering logic, and the debounce queue
- **Debouncing** — the 2-second window and the background polling loop
- **`_process_change`** — wiki vs. non-wiki branching (re-fingerprint vs. auto-node)
- **Daemon lifecycle** — `start`/`stop`/`status` and the PID file mechanism
- **CLI** — all flags with a reference table
