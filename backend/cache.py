import json
from pathlib import Path

from utils.graph.module_graph import analyze_file, compute_file_hash
from utils.rules.rules import get_source_roots


def load_cache(cache_path: str = "result/.scan_cache.json") -> dict:
    p = Path(cache_path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache: dict, cache_path: str = "result/.scan_cache.json"):
    p = Path(cache_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cache, indent=2))


def build_module_graph_incremental(
    root_dir: str,
    files: list[str],
    cache_path: str = "result/.scan_cache.json",
) -> tuple[dict, dict]:
    """Same output shape as build_module_graph(), but reuses cached
    per-file results when the file's content hash is unchanged. Returns
    (result, stats) where stats reports how many files were skipped vs.
    re-analyzed, for visibility into how much the cache actually saved.
    """
    root = Path(root_dir).resolve()
    roots = get_source_roots(root)
    cache = load_cache(cache_path)
    new_cache: dict = {}

    graph = {}
    unresolved_all = []
    function_edges_all = []
    stats = {"cached": 0, "rescanned": 0, "removed_from_cache": 0}

    scanned_files = set()

    for f in files:
        file_path = Path(f)
        if not file_path.is_absolute():
            file_path = file_path.resolve()
        if file_path.suffix != ".py":
            continue

        key = str(file_path)
        scanned_files.add(key)
        current_hash = compute_file_hash(file_path)
        cached_entry = cache.get(key)

        if cached_entry and cached_entry.get("hash") == current_hash:
            stats["cached"] += 1
            imports = cached_entry["imports"]
            unresolved = cached_entry.get("unresolved", [])
            function_edges = cached_entry.get("function_edges", [])
        else:
            stats["rescanned"] += 1
            visitor = analyze_file(file_path, roots)
            imports = visitor.resolved
            unresolved = list(visitor.unresolved)
            function_edges = list(visitor.function_edges)

        graph[key] = {"hash": current_hash, "imports": imports}
        for u in unresolved:
            u = {**u, "file": key}
            unresolved_all.append(u)
        for fe in function_edges:
            fe = {**fe, "file": key}
            function_edges_all.append(fe)

        new_cache[key] = {
            "hash": current_hash,
            "imports": imports,
            "unresolved": unresolved,
            "function_edges": function_edges,
        }

    # Files that were cached before but no longer appear in this scan
    # (deleted, renamed, or newly gitignored) shouldn't linger in the
    # cache forever.
    stats["removed_from_cache"] = len(set(cache.keys()) - scanned_files)

    save_cache(new_cache, cache_path)

    return (
        {
            "graph": graph,
            "unresolved": unresolved_all,
            "function_edges": function_edges_all,
        },
        stats,
    )
