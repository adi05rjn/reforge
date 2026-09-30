# Architecture and trust boundaries

Preferences are the user's desired state. A source snapshot records limited observed state. Diagnostic memory records lessons with explicit applicability conditions. A destination profile describes the target the user intends to rebuild.

The planner validates these inputs, maps approved application IDs to a fixed Debian package catalogue, and excludes applications already listed on the destination. Source inventory is retained as evidence rather than silently becoming desired state.

Diagnostic records are filtered before inference: verified must be true, every declared applicability condition must match, and an unknown machine model cannot establish a match. Correct applicability conditions depend on the user's records; this is not automatic hardware certification.

The optional local model receives only missing application IDs and eligible diagnostics alongside user intent and target context. It chooses an order and highlights relevant records. Its response is rejected unless it matches the exact allowed JSON shape and catalogue-derived action set. Model prose is advisory; there is no command runner.

Only explicitly requested output files are written. Plan generation reserves a new directory and removes its own partial output if inference or writing fails. Existing files are never replaced. Source snapshots and diagnostic records are not automatically committed or uploaded.

## Module map

| Module | Responsibility |
| --- | --- |
| `capture.py` | Read limited Linux metadata and selected config fingerprints |
| `core.py` | Input validation, fixed package mapping, applicability filtering, report rendering |
| `local_ai.py` | Loopback-only HTTP client and model-response validation |
| `cli.py` | Capture, remember and plan workflows; explicit output handling |

## Deliberate limits

Initial natural-language instructions guide local model commentary and priority; structured preferences determine approved applications. Reforge does not yet infer arbitrary software needs, compile software, install packages or recreate a complete desktop. Fingerprints track evidence but cannot restore files. Stored fixes are user assertions, not trusted commands. A future executor must be designed separately with reviewed adapters, capability limits, meaningful verification and recovery.
