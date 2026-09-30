# Reforge

**Carry your workflow, preferences and diagnostic memory into your next Linux installation.**

Reforge is a local-first environment memory and migration planner, developed for the Snapdragon AI project proposal by **adi05rjn**. The long-term goal is to reconstruct a personalised Linux environment from the user's original instructions and lessons learned on previous systems.

**v0.1.0 is a working planning prototype.** It captures a limited Linux inventory, records explicit diagnostic observations, and produces JSON and Markdown migration plans. An optional local language model prioritises the approved applications and highlights applicable diagnostic records. No installation, configuration, kernel or bootloader changes are executed.

## Run the first demo

Python 3.10 or newer is required. The CLI has no third-party runtime dependencies. From this repository's root:

```bash
python -m reforge plan \
  --preferences examples/preferences.json \
  --target examples/target.json \
  --memory examples/memory.json \
  --offline --output my-plan
```

Open `my-plan/plan.md` to see the result. `my-plan/plan.json` is the structured equivalent. The example describes an ARM64 Debian destination with Git already installed. Reforge plans Neovim, ripgrep, an ARM cross compiler and GDB, retains the user's appearance preferences, and excludes a fix recorded for a different laptop. All example records are fictional test fixtures.

`--offline` is deterministic planning, **not AI inference**. Omit it to use an actual local model server. Output files/directories must be new; existing data is never overwritten.

## Capture your source environment

```bash
python -m reforge capture --output my-source.json
python -m reforge plan \
  --source my-source.json \
  --preferences examples/preferences.json \
  --target examples/target.json \
  --offline --output my-source-plan
```

Capture reads Linux distribution/version, architecture, device-tree model when present, availability of six supported applications on PATH, and SHA-256 fingerprints of `.gitconfig` and `.config/nvim/init.lua`. It does not copy configuration contents, hostname, account identifiers or arbitrary logs. Symlinked and oversized configuration files are skipped. Capture is deliberately limited: PATH availability is not a complete package inventory, and model detection can return `unknown`.

The source snapshot is retained as evidence in the plan. It does not silently approve every discovered tool for installation. Edit the preference file to choose the applications you want. Back up original configuration files separately; fingerprints cannot restore their contents. Keep real snapshots and diagnostic files private.

## Record a lesson learned

```bash
python -m reforge remember \
  --output my-memory.json \
  --issue "Editor glyphs are missing" \
  --fix "Review terminal font selection" \
  --outcome "Glyph rendering checked after selecting the correct font" \
  --verified --os-id debian
```

To extend it, pass `--memory my-memory.json --output my-memory-next.json`. Each record needs at least one explicit applicability condition: `--os-id`, `--architecture` or `--machine-model`. Use all relevant conditions for hardware-specific observations. `--verified` is your assertion that you tested the fix, not an automated validation. Unverified and mismatched records are excluded from model context; matching fixes remain advisory and require manual review. Unknown machine models never establish a hardware match.

## Connect a local model

Reforge talks to the local OpenAI-compatible chat-completion endpoint provided by [llama.cpp's server](https://github.com/ggml-org/llama.cpp/tree/master/tools/server). Install/build llama.cpp using its official instructions, obtain a compatible instruction-tuned GGUF model under its own licence, and start it locally, for example:

```bash
llama-server -m /absolute/path/to/model.gguf --host 127.0.0.1 --port 8080
python -m reforge plan \
  --preferences examples/preferences.json \
  --target examples/target.json \
  --memory examples/memory.json \
  --endpoint http://127.0.0.1:8080/v1 \
  --model local-model --output my-ai-plan
```

Set `--model` to the identifier accepted by your server. Model weights and inference runtime are not bundled. Reforge sends user instructions, appearance intent, destination information, approved missing application IDs and eligible diagnostic records to that loopback server. Source config fingerprints are not sent. HTTP proxies and redirects are disabled; non-loopback endpoints are rejected. The local server itself must be operated with appropriate privacy settings.

The model returns a strict JSON object. It may reorder the approved application IDs, select eligible diagnostic IDs, write an advisory summary and ask clarifying questions. It cannot add applications or executable actions. Unknown fields, extra/missing applications and incompatible diagnostic IDs cause the run to fail without a saved plan. Advisory prose is untrusted and should not be treated as instructions to execute.

## Supported today

| Component | v0.1 scope |
| --- | --- |
| Source capture | Linux; six known tools and two config fingerprints |
| Destination | Debian, `aarch64` or `x86_64`; user-supplied target inventory |
| Tool catalogue | Git, Neovim, ripgrep, GCC, GDB, ARM bare-metal GCC |
| Ricing | Theme, editor and keybinding intent retained; no config translation |
| Memory | User-recorded issue, fix, outcome, verification and applicability |
| Local AI | Real HTTP client; model output constrained by deterministic validation |
| Execution | No system changes; reviewable plans only |

For a real target, edit `examples/target.json` to reflect the destination distribution, architecture, exact model if known, and supported applications already available there. Debian package mapping is a proposal, not a repository availability check. Package versions, device support and compiler suitability must be verified on the destination.

## Verify

```bash
python -m unittest discover -s tests -v
```

23 tests cover package planning, hardware applicability, output validation, loopback HTTP integration, capture privacy, memory recording, CLI failures and preservation of existing output. The HTTP integration test uses a fixture server; it does not demonstrate a model's reasoning quality. This release has been tested on the development Linux host. **Snapdragon hardware, actual model inference, NPU acceleration and cross-OS reconstruction have not yet been validated.**

Optional installation into your virtual environment:

```bash
python -m pip install -e .
reforge --help
```

## Next milestones

1. Measure real local-model latency, RAM and plan quality on a Snapdragon Linux laptop; document the exact laptop, distribution, kernel and runtime.
2. Add reviewed user-space application/configuration adapters with backups, diffs, explicit approval and rollback.
3. Add Windows/macOS import and additional Linux package-manager adapters.
4. Restore selected configuration contents through explicit opt-in backup bundles.
5. Introduce narrowly scoped kernel/driver recommendations only after device compatibility, recovery and verification mechanisms exist.

See [architecture](docs/architecture.md), [evaluation plan](docs/evaluation.md) and [project proposal](docs/proposal.md). This repository is a prototype and does not claim competition acceptance or completed Snapdragon optimisation.
