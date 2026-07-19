import argparse

from utils.directory.lookup import get_files_respecting_gitignore
from utils.graph.module_graph import build_module_graph
from overrides import (
    load_overrides,
    save_overrides,
    confirm,
    reject,
    manual_edge,
    detect_orphaned_overrides,
    override_key,
)


def _is_ambiguous_resolved(entry: dict) -> bool:
    """Resolved edges still worth a human's attention: name_inside_module
    guesses (verified only against static top-level names / __all__, not
    runtime behavior) and wildcard imports (multiple names pulled in at
    once, easy to miss what actually landed in scope).
    """
    return (
        entry.get("resolution") == "name_inside_module"
        or entry.get("imported_name") == "*"
    )


def gather_review_items(result: dict) -> list[dict]:
    """Unresolved entries (need a target) + ambiguous resolved entries
    (resolver guessed, worth confirming) + unresolved function_edges
    (Depends()/add_task() calls the local resolver couldn't trace).
    """
    items = list(result.get("unresolved", []))
    for file, node in result.get("graph", {}).items():
        for imp in node.get("imports", []):
            if _is_ambiguous_resolved(imp):
                item = dict(imp)
                item["file"] = file
                items.append(item)
    for fe in result.get("function_edges", []):
        if "resolved_file" not in fe:
            items.append(fe)
    return items


def _print_entry(entry: dict, index: int, total: int):
    print(f"\n[{index}/{total}] {entry.get('file')}:{entry.get('line')}")
    print(f"  kind:      {entry.get('kind')}")
    print(f"  raw:       {entry.get('raw')}")
    if entry.get("imported_name"):
        print(f"  name:      {entry['imported_name']}")
    if entry.get("resolved_file"):
        print(f"  resolved:  {entry['resolved_file']} ({entry.get('resolution')})")
    if entry.get("note"):
        print(f"  note:      {entry['note']}")
    if entry.get("reason"):
        print(f"  reason:    {entry['reason']}")


def run_review(items: list[dict], overrides: dict) -> dict:
    total = len(items)
    for i, entry in enumerate(items, start=1):
        _print_entry(entry, i, total)
        while True:
            choice = (
                input("  [c]onfirm  [r]eject  [m]anual edge  [s]kip  [q]uit: ")
                .strip()
                .lower()
            )
            if choice == "c":
                if not entry.get("resolved_file"):
                    target = input(
                        "  no existing resolution — target file path: "
                    ).strip()
                    overrides = confirm(overrides, entry, resolved_file=target)
                else:
                    overrides = confirm(overrides, entry)
                break
            elif choice == "r":
                overrides = reject(overrides, entry)
                break
            elif choice == "m":
                target = input("  target file path: ").strip()
                overrides = manual_edge(overrides, entry, target)
                break
            elif choice == "s":
                break
            elif choice == "q":
                return overrides
            else:
                print("  (unrecognized input, try again)")
    return overrides


def main():
    parser = argparse.ArgumentParser(
        description="Interactive review of unresolved/ambiguous imports"
    )
    parser.add_argument("project_root")
    parser.add_argument("--overrides", default="overrides.json")
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="re-show items that already have a decision",
    )
    parser.add_argument(
        "--prune-orphaned",
        action="store_true",
        help="remove overrides that no longer match anything in this scan",
    )
    args = parser.parse_args()

    files = get_files_respecting_gitignore(args.project_root)
    result = build_module_graph(args.project_root, files)

    overrides = load_overrides(args.overrides)

    orphaned = detect_orphaned_overrides(overrides, result)
    if orphaned:
        print(
            f"\u26a0 {len(orphaned)} override(s) no longer match the current "
            "scan (orphaned):"
        )
        for key in orphaned:
            print(f"  - {key}")
        if args.prune_orphaned:
            for key in orphaned:
                overrides.pop(key, None)
            print("  pruned.\n")
        else:
            print("  (re-run with --prune-orphaned to remove them)\n")

    items = gather_review_items(result)
    if args.show_all:
        pending = items
    else:
        decided = set(overrides.keys())
        pending = [
            e
            for e in items
            if override_key(
                e.get("file", ""),
                e.get("line", -1),
                e.get("raw", ""),
                e.get("imported_name"),
            )
            not in decided
        ]

    if not pending:
        print(
            "Nothing to review — every unresolved/ambiguous item already "
            "has a decision (use --show-all to re-review)."
        )
        save_overrides(overrides, args.overrides)
        return

    print(
        f"{len(pending)} item(s) need review "
        f"({len(items) - len(pending)} already decided)."
    )
    overrides = run_review(pending, overrides)
    save_overrides(overrides, args.overrides)
    print(f"\nSaved decisions to {args.overrides}")


if __name__ == "__main__":
    main()
