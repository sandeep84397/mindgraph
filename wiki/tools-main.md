# Tools CLI Entry Point

## Summary
`tools/__main__.py` — CLI dispatcher, MindGraph toolchain. `python3 -m tools <subcommand> [args]`. Subcommand → module, dynamic import, call `main()`.

## Details

### Command Registry
`COMMANDS` dict: subcommand → dotted module path.

| Subcommand | Module |
|---|---|
| `init` | `tools.init_kb` |
| `fingerprint` | `tools.fingerprint` |
| `search` | `tools.search` |
| `ingest` | `tools.ingest` |
| `lint` | `tools.lint` |
| `watch` | `tools.watch` |
| `stats` | `tools.stats` |

### Dispatch Flow
1. No subcommand or `-h`/`--help` → print usage, exit.
2. Unknown subcommand → exit error.
3. Strip subcommand from `sys.argv`; module sees own args at `sys.argv[0]`.
4. `__import__` target module, call `main()`.

### Help Output
`python3 -m tools` or `python3 -m tools --help`:
```
Usage: python3 -m tools <subcommand> [args]

Subcommands: init, fingerprint, search, ingest, lint, watch, stats
```

## References
- `tools/__main__.py`

## See Also
- [[Tools Init]]
- [[Tools Fingerprint]]
- [[Tools Search]]
- [[MindGraph Schema]]
