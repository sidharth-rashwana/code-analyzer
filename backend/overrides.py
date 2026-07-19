import json
from pathlib import Path


def override_key(
    file: str, line: int, raw: str, imported_name: str | None = None
) -> str:
    """Stable identity for a single import occurrence."""
    suffix = f":{imported_name}" if imported_name else ""
    return f"{file}:{line}:{raw}{suffix}"


def _key_for_entry(entry: dict) -> str:
    return override_key(
        entry.get("file", ""),
        entry.get("line", -1),
        entry.get("raw", ""),
        entry.get("imported_name"),
    )


def load_overrides(path: str = "overrides.json") -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def save_overrides(overrides: dict, path: str = "overrides.json"):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(overrides, indent=2))


def _record(entry: dict, decision: str, **extra) -> dict:
    return {
        "decision": decision,
        "file": entry.get("file", ""),
        "line": entry.get("line", -1),
        "raw": entry.get("raw", ""),
        "imported_name": entry.get("imported_name"),
        **extra,
    }


def confirm(overrides: dict, entry: dict, resolved_file: str | None = None) -> dict:
    """Accept the entry's current resolution as correct. If the entry was
    unresolved, `resolved_file` supplies the target (otherwise required).
    """
    target = resolved_file or entry.get("resolved_file")
    overrides[_key_for_entry(entry)] = _record(entry, "confirm", resolved_file=target)
    return overrides


def reject(overrides: dict, entry: dict, reason: str | None = None) -> dict:
    """Mark a resolved edge as wrong — apply_overrides() will strip it
    out of the graph on the next application.
    """
    overrides[_key_for_entry(entry)] = _record(
        entry, "reject", reason=reason or "manually rejected during review"
    )
    return overrides


def manual_edge(overrides: dict, entry: dict, target_file: str) -> dict:
    """Supply a target file by hand for an import the resolver couldn't
    figure out (or got wrong) — e.g. dynamic imports, DI-injected
    dependencies the static resolver can't trace.
    """
    overrides[_key_for_entry(entry)] = _record(
        entry, "manual", resolved_file=target_file
    )
    return overrides


def apply_overrides(result: dict, overrides: dict) -> dict:
    """Apply stored decisions onto a fresh build_module_graph() result:
      - confirm / manual (with a resolved_file): if the matching entry is
        currently unresolved, promote it into that file's "imports" list.
        Already-resolved entries are left as-is (nothing to promote).
      - reject: strip the matching entry out of its file's "imports" list.
    Entries without a matching override pass through untouched. Returns a
    new dict; `result` is not mutated.
    """
    import copy

    result = copy.deepcopy(result)

    still_unresolved = []
    for u in result.get("unresolved", []):
        override = overrides.get(_key_for_entry(u))
        if (
            override
            and override["decision"] in ("confirm", "manual")
            and override.get("resolved_file")
        ):
            file = u.get("file", "")
            node = result["graph"].setdefault(file, {"hash": None, "imports": []})
            promoted = dict(u)
            promoted["resolved_file"] = override["resolved_file"]
            promoted["resolution"] = f"override:{override['decision']}"
            promoted.pop("reason", None)
            node["imports"].append(promoted)
        else:
            still_unresolved.append(u)
    result["unresolved"] = still_unresolved

    for file, node in result.get("graph", {}).items():
        kept = []
        for imp in node.get("imports", []):
            imp_with_file = {**imp, "file": file}
            override = overrides.get(_key_for_entry(imp_with_file))
            if override and override["decision"] == "reject":
                continue
            kept.append(imp)
        node["imports"] = kept

    return result


def _all_current_keys(result: dict) -> set:
    keys = set()
    for u in result.get("unresolved", []):
        keys.add(_key_for_entry(u))
    for file, node in result.get("graph", {}).items():
        for imp in node.get("imports", []):
            keys.add(_key_for_entry({**imp, "file": file}))
    for fe in result.get("function_edges", []):
        keys.add(_key_for_entry(fe))
    return keys


def detect_orphaned_overrides(overrides: dict, result: dict) -> list[str]:
    """Report overrides whose underlying import no longer matches
    anything in a fresh scan result — the line moved, the raw import
    text changed, or the import was removed entirely. Report-only: does
    not delete anything, so a human notices before the decision silently
    stops applying (see prune_orphaned_overrides to actually remove them).
    """
    current_keys = _all_current_keys(result)
    return [key for key in overrides if key not in current_keys]


def prune_orphaned_overrides(overrides: dict, result: dict) -> dict:
    """Remove orphaned overrides (see detect_orphaned_overrides) in place
    and return the pruned dict. Call this explicitly — orphaning is
    reported by default, not auto-deleted.
    """
    for key in detect_orphaned_overrides(overrides, result):
        overrides.pop(key, None)
    return overrides
