"""Pure validation and planning. No shell commands or system mutations."""
import json

CATALOG = {
    "git": "git", "neovim": "neovim", "ripgrep": "ripgrep",
    "gcc": "gcc", "gdb": "gdb", "arm-none-eabi-gcc": "gcc-arm-none-eabi",
}
CONDITIONS = {"os_id", "architecture", "machine_model"}


class ReforgeError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReforgeError(message)


def exact(obj, keys, label):
    require(isinstance(obj, dict) and set(obj) == set(keys),
            f"{label}: expected fields {', '.join(sorted(keys))}")


def text(value, label, limit=2000):
    require(isinstance(value, str) and 0 < len(value.strip()) <= limit,
            f"{label}: expected non-empty text (maximum {limit} characters)")
    return value


def apps(value, label):
    require(isinstance(value, list) and all(isinstance(x, str) for x in value),
            f"{label}: expected a list of application IDs")
    require(len(value) == len(set(value)) and set(value) <= set(CATALOG),
            f"{label}: duplicate or unknown application; supported: {', '.join(CATALOG)}")


def validate_preferences(p):
    exact(p, {"schema_version", "instructions", "applications", "appearance"}, "preferences")
    require(type(p["schema_version"]) is int and p["schema_version"] == 1, "unsupported preference schema")
    text(p["instructions"], "instructions", 8000)
    apps(p["applications"], "applications")
    exact(p["appearance"], {"theme", "editor", "keybindings"}, "appearance")
    for key, value in p["appearance"].items():
        text(value, key, 200)
    return p


def validate_target(t):
    exact(t, {"os_id", "architecture", "machine_model", "installed_applications"}, "target")
    require(t["os_id"] == "debian", "v0.1 plans target Debian only")
    require(isinstance(t["architecture"], str) and t["architecture"] in {"aarch64", "x86_64"}, "supported target architectures: aarch64, x86_64")
    text(t["machine_model"], "machine_model", 200)
    apps(t["installed_applications"], "installed_applications")
    return t


def validate_memory(m):
    exact(m, {"schema_version", "records"}, "memory")
    require(type(m["schema_version"]) is int and m["schema_version"] == 1, "unsupported memory schema")
    require(isinstance(m["records"], list) and len(m["records"]) <= 100, "memory supports at most 100 records")
    ids = set()
    for r in m["records"]:
        exact(r, {"id", "issue", "fix", "outcome", "verified", "conditions"}, "record")
        for key in ("id", "issue", "fix", "outcome"):
            text(r[key], key)
        require(r["id"] not in ids, "duplicate diagnostic ID")
        ids.add(r["id"])
        require(type(r["verified"]) is bool, "verified must be boolean")
        c = r["conditions"]
        require(isinstance(c, dict) and bool(c) and set(c) <= CONDITIONS,
                "diagnostics require explicit os_id, architecture or machine_model conditions")
        for key, value in c.items():
            text(value, key, 200)
    return m


def baseline(preferences, target, memory):
    validate_preferences(preferences)
    validate_target(target)
    validate_memory(memory)
    actions = [{"operation": "install_package", "application": app, "package": CATALOG[app]}
               for app in preferences["applications"] if app not in target["installed_applications"]]
    eligible, skipped = [], []
    for r in memory["records"]:
        if not r["verified"]:
            skipped.append({"id": r["id"], "reason": "fix not verified"})
        elif any(target.get(k) != v or (k == "machine_model" and v == "unknown") for k, v in r["conditions"].items()):
            skipped.append({"id": r["id"], "reason": "target does not match applicability conditions"})
        else:
            eligible.append(r)
    return {
        "schema_version": 1, "mode": "offline", "target": target,
        "actions": actions, "preserved_preferences": preferences["appearance"],
        "diagnostics_for_review": eligible, "skipped_diagnostics": skipped,
        "ai": None,
        "limitations": ["Plan only: no installation or configuration is executed.",
                        "Appearance and keybindings are preserved as intent; translation is not implemented.",
                        "Diagnostic fixes require manual review, even when conditions match.",
                        "Kernel, bootloader and driver changes are outside v0.1."],
    }


def attach_source(plan, snapshot):
    exact(snapshot, {"schema_version", "os_id", "os_version", "architecture", "machine_model",
                     "installed_applications", "config_fingerprints"}, "source snapshot")
    require(type(snapshot["schema_version"]) is int and snapshot["schema_version"] == 1, "unsupported snapshot schema")
    for key in ("os_id", "os_version", "architecture", "machine_model"):
        text(snapshot[key], key, 200)
    apps(snapshot["installed_applications"], "snapshot applications")
    fingerprints = snapshot["config_fingerprints"]
    require(isinstance(fingerprints, dict) and set(fingerprints) <= {"neovim", "git"}, "unknown configuration fingerprint")
    for value in fingerprints.values():
        exact(value, {"relative_path", "sha256"}, "fingerprint")
        text(value["relative_path"], "relative_path", 200)
        digest = value["sha256"]
        require(isinstance(digest, str) and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "invalid config digest")
    # Snapshot data is evidence, not instructions; only preferences approve packages.
    plan["source_snapshot"] = snapshot
    return plan


def validate_ai(response, plan):
    """Model may order approved applications and select eligible memory, never invent actions."""
    exact(response, {"summary", "application_order", "diagnostic_ids", "questions"}, "model response")
    text(response["summary"], "summary")
    order = response["application_order"]
    expected = [a["application"] for a in plan["actions"]]
    require(isinstance(order, list) and all(isinstance(x, str) for x in order)
            and len(order) == len(set(order)) and set(order) == set(expected),
            "model application_order must contain exactly the approved missing applications")
    ids = response["diagnostic_ids"]
    allowed = {r["id"] for r in plan["diagnostics_for_review"]}
    require(isinstance(ids, list) and all(isinstance(x, str) for x in ids)
            and len(ids) == len(set(ids)) and set(ids) <= allowed,
            "model selected an inapplicable or unknown diagnostic")
    require(isinstance(response["questions"], list) and len(response["questions"]) <= 10,
            "questions must be a list of at most 10 items")
    for question in response["questions"]:
        text(question, "question", 1000)
    by_app = {a["application"]: a for a in plan["actions"]}
    plan["actions"] = [by_app[app] for app in order]
    plan["ai"] = response
    plan["mode"] = "local_ai"
    return plan


def report(plan):
    lines = ["# Reforge migration plan", "", f"Mode: {plan['mode']}",
             f"Target: {plan['target']['os_id']} / {plan['target']['architecture']}", "",
             "## Approved package plan", ""]
    lines += [f"- {a['application']}: Debian package `{a['package']}`" for a in plan["actions"]] or ["No missing applications."]
    lines += ["", "## Preserved personalisation intent", ""]
    lines += [f"- {k}: {v}" for k, v in plan["preserved_preferences"].items()]
    if "source_snapshot" in plan:
        source = plan["source_snapshot"]
        lines += ["", "## Source environment evidence", "",
                  f"Source: {source['os_id']} {source['os_version']} / {source['architecture']}",
                  "Config fingerprints retained for comparison; original files must be backed up separately."]
        lines += [f"- {app}: `{item['relative_path']}` SHA-256 `{item['sha256']}`"
                  for app, item in source["config_fingerprints"].items()]
    lines += ["", "## Diagnostic memory", ""]
    selected = set(plan["ai"]["diagnostic_ids"]) if plan["ai"] else set()
    for r in plan["diagnostics_for_review"]:
        lines += [f"- {r['id']}: {r['issue']}", f"  Recorded fix (manual review): {r['fix']}",
                  f"  Outcome: {r['outcome']}; model highlighted: {r['id'] in selected}"]
    lines += [f"- Skipped {r['id']}: {r['reason']}" for r in plan["skipped_diagnostics"]]
    if plan["ai"]:
        lines += ["", "## Local model commentary (untrusted advisory text)", "", plan["ai"]["summary"]]
        lines += [f"- Question: {q}" for q in plan["ai"]["questions"]]
    lines += ["", "## Limits", ""] + [f"- {s}" for s in plan["limitations"]]
    return "\n".join(lines) + "\n"


def load(path):
    with open(path, encoding="utf-8") as stream:
        raw = stream.read(1_000_001)
    require(len(raw) <= 1_000_000, "input exceeds 1 MB")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReforgeError(f"invalid JSON in {path}: {exc.msg}") from exc
