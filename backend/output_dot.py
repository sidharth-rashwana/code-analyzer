from pathlib import Path


def _node_label(file_path: str, root_dir: str) -> str:
    try:
        return str(Path(file_path).relative_to(Path(root_dir).resolve()))
    except ValueError:
        return file_path


def _escape(s: str) -> str:
    return s.replace('"', '\\"')


def to_dot(result: dict, root_dir: str, include_unresolved: bool = False) -> str:
    """Module-level import graph as DOT. Nodes are files (labeled
    relative to root_dir for readability), edges are resolved imports.
    Unresolved imports are omitted by default (there's no target node to
    draw an edge to) — pass include_unresolved=True to instead draw them
    as red edges into a synthetic "<unresolved>" node, grouped by reason.
    """
    lines = ["digraph module_graph {", '  rankdir="LR";', "  node [shape=box];"]

    nodes = set(result.get("graph", {}).keys())
    edges: list[tuple[str, str]] = []
    for file, node in result.get("graph", {}).items():
        for imp in node.get("imports", []):
            target = imp.get("resolved_file")
            if target:
                nodes.add(target)
                edges.append((file, target))

    for n in sorted(nodes):
        label = _escape(_node_label(n, root_dir))
        lines.append(f'  "{_escape(n)}" [label="{label}"];')

    for src, dst in edges:
        lines.append(f'  "{_escape(src)}" -> "{_escape(dst)}";')

    if include_unresolved:
        lines.append(
            '  "<unresolved>" [shape=octagon, color=red, '
            'label="unresolved imports"];'
        )
        for u in result.get("unresolved", []):
            src = u.get("file")
            if src:
                label = _escape(u.get("imported_name") or u.get("raw", "?"))
                lines.append(
                    f'  "{_escape(src)}" -> "<unresolved>" '
                    f'[color=red, fontcolor=red, label="{label}"];'
                )

    lines.append("}")
    return "\n".join(lines)


def save_dot(
    result: dict,
    root_dir: str,
    output_path: str = "result/module_graph.dot",
    include_unresolved: bool = False,
):
    content = to_dot(result, root_dir, include_unresolved)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path
