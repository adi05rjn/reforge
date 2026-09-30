import argparse
import json
import sys
import uuid
from pathlib import Path

from .capture import capture
from .core import ReforgeError, attach_source, baseline, load, report, validate_memory
from .local_ai import enrich


def write_new(path, content):
    # Explicit output files only. Never overwrite a user's existing file.
    with open(path, "x", encoding="utf-8") as stream:
        stream.write(content)


def json_text(value):
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reforge v0.1 — local memory and migration plans; no system changes")
    commands = parser.add_subparsers(dest="command", required=True)
    c = commands.add_parser("capture", help="read-only Linux snapshot; no configuration contents")
    c.add_argument("--output", required=True)
    d = commands.add_parser("remember", help="append an explicitly recorded diagnosis to a new memory file")
    d.add_argument("--memory", help="existing memory input; omitted starts an empty memory")
    d.add_argument("--output", required=True)
    for field in ("issue", "fix", "outcome"):
        d.add_argument(f"--{field}", required=True)
    d.add_argument("--verified", action="store_true", help="you have tested the fix and recorded its outcome")
    for field in ("os-id", "architecture", "machine-model"):
        d.add_argument(f"--{field}")
    p = commands.add_parser("plan", help="generate validated JSON and Markdown plans")
    for field in ("preferences", "target", "output"):
        p.add_argument(f"--{field}", required=True)
    p.add_argument("--memory")
    p.add_argument("--source", help="optional Linux capture snapshot retained as environment evidence")
    p.add_argument("--offline", action="store_true", help="deterministic plan without AI; clearly labelled")
    p.add_argument("--endpoint", default="http://127.0.0.1:8080/v1")
    p.add_argument("--model", default="local-model", help="model ID accepted by your local server")
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            write_new(args.output, json_text(capture()))
            print(f"Read-only snapshot written to {args.output}")
        elif args.command == "remember":
            m = load(args.memory) if args.memory else {"schema_version": 1, "records": []}
            validate_memory(m)
            conditions = {k: getattr(args, k) for k in ("os_id", "architecture", "machine_model") if getattr(args, k)}
            m["records"].append({"id": uuid.uuid4().hex, "issue": args.issue,
                                 "fix": args.fix, "outcome": args.outcome,
                                 "verified": args.verified, "conditions": conditions})
            validate_memory(m)
            write_new(args.output, json_text(m))
            print(f"Diagnostic memory written to {args.output}")
        else:
            prefs, target = load(args.preferences), load(args.target)
            memory = load(args.memory) if args.memory else {"schema_version": 1, "records": []}
            plan = baseline(prefs, target, memory)
            if args.source:
                attach_source(plan, load(args.source))
            output = Path(args.output)
            # Reserve a fresh directory before expensive inference. A failed run removes it.
            output.mkdir(parents=False, exist_ok=False)
            try:
                if not args.offline:
                    plan = enrich(plan, prefs, args.endpoint, args.model)
                write_new(output / "plan.json", json_text(plan))
                write_new(output / "plan.md", report(plan))
            except Exception:
                # Only these newly-created files can be removed; no pre-existing paths touched.
                for name in ("plan.json", "plan.md"):
                    (output / name).unlink(missing_ok=True)
                output.rmdir()
                raise
            print(f"{plan['mode']} plan written to {output}; no system changes executed")
        return 0
    except (ReforgeError, OSError) as exc:
        print(f"reforge: {exc}", file=sys.stderr)
        return 2
