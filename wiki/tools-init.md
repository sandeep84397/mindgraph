# Tools Package Init

## Summary
`tools` package entry. Bootstrap `sys.path` for Caveman. Detect `caveman/caveman-compress`, prepend to `sys.path`. Runs on import.

## Details

### Caveman Path Resolution
`Path(__file__).parent.parent / "caveman" / "caveman-compress"`. Portable across clone locations.

### Conditional Injection
Inject if: dir exists AND not in `sys.path`. No duplicate entries.

### Side-Effect-Only Module
No exports. Only `sys.path` mutation.

## References
- `tools/__init__.py`

## See Also
- [[Tools Main]]
- [[Tools Search]]
- [[Schema]]
