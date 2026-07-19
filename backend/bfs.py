from collections import deque

from utils.graph.function_graph import build_function_graph


def _bfs(adjacency: dict[str, list[str]], start: str, max_depth: int | None = None):
    """Generic BFS returning {node_id: depth} for every node reachable
    from `start` (start itself excluded), respecting max_depth if given.
    """
    if start not in adjacency and start not in {
        n for neighbors in adjacency.values() for n in neighbors
    }:
        return {}

    visited: dict[str, int] = {}
    queue = deque([(start, 0)])
    seen = {start}

    while queue:
        node, depth = queue.popleft()
        if max_depth is not None and depth >= max_depth:
            continue
        for neighbor in adjacency.get(node, []):
            if neighbor not in seen:
                seen.add(neighbor)
                visited[neighbor] = depth + 1
                queue.append((neighbor, depth + 1))

    return visited


def _forward_adjacency(function_graph: dict) -> dict[str, list[str]]:
    return {fid: node.get("calls", []) for fid, node in function_graph.items()}


def _reverse_adjacency(function_graph: dict) -> dict[str, list[str]]:
    reverse: dict[str, list[str]] = {fid: [] for fid in function_graph}
    for fid, node in function_graph.items():
        for callee in node.get("calls", []):
            reverse.setdefault(callee, []).append(fid)
    return reverse


def callees(
    function_graph: dict, start: str, max_depth: int | None = None
) -> dict[str, int]:
    """Everything `start` transitively calls. Returns {function_id: depth}.
    depth=1 is a direct call, depth=2 is a call from something start
    calls, etc. Use max_depth=1 for direct-impact-only (Roadmap item 1).
    """
    return _bfs(_forward_adjacency(function_graph), start, max_depth)


def callers(
    function_graph: dict, target: str, max_depth: int | None = None
) -> dict[str, int]:
    """Everything that transitively calls `target` — the blast radius of
    changing it. Returns {function_id: depth}, depth=1 is a direct caller.
    Use max_depth=1 for direct-impact-only (Roadmap item 1); omit
    max_depth for full transitive impact (Roadmap item 2).
    """
    return _bfs(_reverse_adjacency(function_graph), target, max_depth)


def blast_radius(function_graph: dict, changed_functions: list[str]) -> dict:
    """Convenience wrapper for the common "I changed these functions,
    what do I need to feed the LLM" case. Returns per-function direct +
    transitive callers, plus a deduped union across all of them.
    """
    result = {}
    union: set[str] = set()
    for fid in changed_functions:
        reached = callers(function_graph, fid)
        result[fid] = {
            "direct_callers": sorted(f for f, d in reached.items() if d == 1),
            "all_transitive_callers": sorted(reached.keys()),
        }
        union.update(reached.keys())
    result["_union_all_affected"] = sorted(union)
    return result


def build_and_analyze(
    files: list[str], root_dir: str, changed_functions: list[str]
) -> dict:
    """End-to-end convenience: build the function graph fresh, then run
    blast_radius against it.
    """
    fg = build_function_graph(files, root_dir)
    return blast_radius(fg, changed_functions)
