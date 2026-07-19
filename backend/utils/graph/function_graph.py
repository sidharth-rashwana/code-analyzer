import ast
from pathlib import Path

from utils.rules.rules import get_source_roots


def function_id(file: str, qualname: str) -> str:
    return f"{file}::{qualname}"


def _find_def_node(body: list[ast.stmt], qual_parts: list[str]) -> ast.AST | None:
    """Walk a module/class body (recursing into nested classes) looking
    for the def matching qual_parts, e.g. ["foo"] for a top-level
    function or ["Outer", "Inner", "method"] for a nested one. Mirrors
    the class_stack join used when defs are first collected below, so a
    qualname produced by this module can always be looked back up.
    """
    target_name = qual_parts[0]
    for node in body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == target_name
            and len(qual_parts) == 1
        ):
            return node
        if isinstance(node, ast.ClassDef) and node.name == target_name:
            if len(qual_parts) == 1:
                continue  # qualname pointed at the class itself, not a def
            found = _find_def_node(node.body, qual_parts[1:])
            if found is not None:
                return found
    return None


def _parse_and_find(file_path: Path, qualname: str) -> tuple[str, ast.AST] | tuple[None, None]:
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(file_path))
    except (OSError, SyntaxError):
        return None, None
    node = _find_def_node(tree.body, qualname.split("."))
    if node is None:
        return None, None
    return source, node


def extract_function_source(file_path: Path, qualname: str) -> str | None:
    """Exact source text of a single function/method (by qualname, as
    produced by function_id()/build_function_graph). Returns None if it
    can't be found (e.g. the file changed since the graph was built).
    """
    source, node = _parse_and_find(file_path, qualname)
    if node is None:
        return None
    return ast.get_source_segment(source, node)


def extract_function_signature(file_path: Path, qualname: str) -> str | None:
    """Signature-only stub — `def name(args) -> ret: ...` without the
    body — for budget-constrained context bundles that can't afford the
    full source of every relevant function. Returns None if not found.
    """
    _, node = _parse_and_find(file_path, qualname)
    if node is None:
        return None
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    args = ast.unparse(node.args)
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{prefix} {node.name}({args}){returns}: ..."


def extract_function_line_range(file_path: Path, qualname: str) -> tuple[int, int] | None:
    """(start_line, end_line) of the def, 1-indexed inclusive — used e.g.
    to scope a `git blame` lookup to just this function's lines. Returns
    None if not found.
    """
    _, node = _parse_and_find(file_path, qualname)
    if node is None:
        return None
    return node.lineno, node.end_lineno


def _collect_defs_and_import_map(
    tree: ast.Module, file_path: Path, roots: list[Path]
) -> tuple[dict[str, ast.AST], dict[str, dict]]:
    from utils.rules.rules import (
        file_to_module_parts,
        resolve_import,
        resolve_import_from,
    )

    current_module_parts = file_to_module_parts(file_path, roots)
    import_map: dict[str, dict] = {}
    defs: dict[str, ast.AST] = {}
    class_stack: list[str] = []

    def walk_class(node: ast.ClassDef):
        class_stack.append(node.name)
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs[".".join(class_stack + [child.name])] = child
            elif isinstance(child, ast.ClassDef):
                walk_class(child)
        class_stack.pop()

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs[node.name] = node
        elif isinstance(node, ast.ClassDef):
            walk_class(node)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                entry = resolve_import(alias, roots)
                bound = alias.asname or alias.name.split(".")[0]
                import_map[bound] = {
                    "resolved_file": entry.get("resolved_file"),
                    "raw": entry.get("raw"),
                }
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                entry = resolve_import_from(
                    alias,
                    module=node.module,
                    level=node.level,
                    current_module_parts=current_module_parts,
                    root=roots,
                )
                if alias.name == "*":
                    for name in entry.get("exported_names", []):
                        import_map[name] = {
                            "resolved_file": entry.get("resolved_file"),
                            "raw": f"{entry.get('raw')}.{name}",
                        }
                else:
                    bound = alias.asname or alias.name
                    import_map[bound] = {
                        "resolved_file": entry.get("resolved_file"),
                        "raw": entry.get("raw"),
                    }

    return defs, import_map


def _extract_call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def build_function_graph(files: list[str], root_dir: str) -> dict:
    """
    Returns:
      {
        "<file>::<qualname>": {
          "file": "<file>", "name": "<qualname>",
          "calls": ["<file>::<qualname>", ...],   # resolved callees
          "unresolved_calls": [{"raw": ..., "line": ...}, ...]
        }, ...
      }
    """
    root = Path(root_dir).resolve()
    roots = get_source_roots(root)
    graph: dict[str, dict] = {}

    per_file: dict[str, tuple[dict, dict]] = {}
    for f in files:
        file_path = Path(f)
        if not file_path.is_absolute():
            file_path = file_path.resolve()
        if file_path.suffix != ".py":
            continue
        source = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(file_path))
        defs, import_map = _collect_defs_and_import_map(tree, file_path, roots)
        per_file[str(file_path)] = (defs, import_map)
        for qualname in defs:
            fid = function_id(str(file_path), qualname)
            graph[fid] = {
                "file": str(file_path),
                "name": qualname,
                "calls": [],
                "unresolved_calls": [],
            }

    for file_str, (defs, import_map) in per_file.items():
        same_file_qualnames = set(defs.keys())
        method_names = {q.split(".")[-1]: q for q in defs if "." in q}

        for qualname, func_node in defs.items():
            caller_fid = function_id(file_str, qualname)
            for child in ast.walk(func_node):
                if child is func_node:
                    continue
                if not isinstance(child, ast.Call):
                    continue
                call_name = _extract_call_name(child.func)
                if call_name is None:
                    graph[caller_fid]["unresolved_calls"].append(
                        {
                            "raw": ast.dump(child.func)[:80],
                            "line": child.lineno,
                            "reason": "callee is not a simple name/attribute",
                        }
                    )
                    continue

                if call_name in same_file_qualnames:
                    callee_fid = function_id(file_str, call_name)
                    graph[caller_fid]["calls"].append(callee_fid)
                elif call_name in method_names:
                    callee_fid = function_id(file_str, method_names[call_name])
                    graph[caller_fid]["calls"].append(callee_fid)
                elif call_name in import_map and import_map[call_name].get(
                    "resolved_file"
                ):
                    target_file = import_map[call_name]["resolved_file"]
                    target_defs = per_file.get(target_file, ({}, {}))[0]
                    if call_name in target_defs:
                        callee_fid = function_id(target_file, call_name)
                        graph[caller_fid]["calls"].append(callee_fid)
                    else:
                        graph[caller_fid]["unresolved_calls"].append(
                            {
                                "raw": call_name,
                                "line": child.lineno,
                                "reason": (
                                    f"imported from {target_file} but not "
                                    "found among its function/method defs"
                                ),
                            }
                        )
                else:
                    graph[caller_fid]["unresolved_calls"].append(
                        {
                            "raw": call_name,
                            "line": child.lineno,
                            "reason": (
                                "not found among this file's imports, "
                                "same-file defs, or same-class methods"
                            ),
                        }
                    )

    return graph
