import json
from pathlib import Path


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text())


def _edge_set(imports: list[dict]) -> set[tuple]:
    """Reduce each import entry to a hashable identity for set-diffing:
    (kind, raw, imported_name, alias, resolved_file). Two scans' import
    lists are compared as sets of these tuples rather than by list
    position or line number — import order/line position shifts on
    almost any edit and isn't semantically meaningful, but `alias` must
    be included or two distinct bindings of the same name (e.g. a plain
    import plus a newly added aliased one) collide into a single tuple
    and the added one goes undetected.
    """
    return {
        (
            imp.get("kind"),
            imp.get("raw"),
            imp.get("imported_name"),
            imp.get("alias"),
            imp.get("resolved_file"),
        )
        for imp in imports
    }


def diff_snapshots(old: dict, new: dict) -> dict:
    """Returns:
    {
      "files_added": [...], "files_removed": [...],
      "files_changed": [...],   # hash differs
      "edges": {
        "<file>": {"added": [...], "removed": [...]}
      },
      "unresolved_added": [...], "unresolved_removed": [...],
    }
    """
    old_graph = old.get("graph", {})
    new_graph = new.get("graph", {})

    old_files = set(old_graph.keys())
    new_files = set(new_graph.keys())

    files_added = sorted(new_files - old_files)
    files_removed = sorted(old_files - new_files)
    files_changed = sorted(
        f
        for f in old_files & new_files
        if old_graph[f].get("hash") != new_graph[f].get("hash")
    )

    edges_diff = {}
    for f in sorted(old_files | new_files):
        old_edges = _edge_set(old_graph.get(f, {}).get("imports", []))
        new_edges = _edge_set(new_graph.get(f, {}).get("imports", []))
        added = new_edges - old_edges
        removed = old_edges - new_edges
        if added or removed:
            edges_diff[f] = {
                "added": [
                    {
                        "kind": k,
                        "raw": r,
                        "imported_name": n,
                        "alias": a,
                        "resolved_file": rf,
                    }
                    for (k, r, n, a, rf) in sorted(added, key=lambda t: str(t))
                ],
                "removed": [
                    {
                        "kind": k,
                        "raw": r,
                        "imported_name": n,
                        "alias": a,
                        "resolved_file": rf,
                    }
                    for (k, r, n, a, rf) in sorted(removed, key=lambda t: str(t))
                ],
            }

    def _unresolved_key(u: dict) -> tuple:
        return (u.get("file"), u.get("line"), u.get("raw"), u.get("imported_name"))

    old_unresolved = {_unresolved_key(u): u for u in old.get("unresolved", [])}
    new_unresolved = {_unresolved_key(u): u for u in new.get("unresolved", [])}
    unresolved_added = [
        new_unresolved[k] for k in new_unresolved.keys() - old_unresolved.keys()
    ]
    unresolved_removed = [
        old_unresolved[k] for k in old_unresolved.keys() - new_unresolved.keys()
    ]

    return {
        "files_added": files_added,
        "files_removed": files_removed,
        "files_changed": files_changed,
        "edges": edges_diff,
        "unresolved_added": unresolved_added,
        "unresolved_removed": unresolved_removed,
    }


def diff_files(old_path: str, new_path: str) -> dict:
    return diff_snapshots(_load(old_path), _load(new_path))


def format_diff_text(diff: dict) -> str:
    lines = []
    if diff["files_added"]:
        lines.append(f"Files added ({len(diff['files_added'])}):")
        lines += [f"  + {f}" for f in diff["files_added"]]
    if diff["files_removed"]:
        lines.append(f"Files removed ({len(diff['files_removed'])}):")
        lines += [f"  - {f}" for f in diff["files_removed"]]
    files_changed_no_edge_diff = [
        f for f in diff["files_changed"] if f not in diff["edges"]
    ]
    if files_changed_no_edge_diff:
        lines.append(
            f"Files changed, no import-level differences "
            f"({len(files_changed_no_edge_diff)}):"
        )
        lines += [f"  ~ {f}" for f in files_changed_no_edge_diff]
    if diff["edges"]:
        lines.append("Import changes:")
        for file, changes in diff["edges"].items():
            lines.append(f"  {file}")
            for e in changes["added"]:
                lines.append(f"    + {e['kind']} {e['raw']} ({e['imported_name']})")
            for e in changes["removed"]:
                lines.append(f"    - {e['kind']} {e['raw']} ({e['imported_name']})")
    if diff["unresolved_added"]:
        lines.append(f"New unresolved imports ({len(diff['unresolved_added'])}):")
        for u in diff["unresolved_added"]:
            lines.append(f"  ! {u.get('file')}:{u.get('line')} {u.get('raw')}")
    if not any(
        [
            diff["files_added"],
            diff["files_removed"],
            files_changed_no_edge_diff,
            diff["edges"],
            diff["unresolved_added"],
            diff["unresolved_removed"],
        ]
    ):
        lines.append("No differences.")
    return "\n".join(lines)
