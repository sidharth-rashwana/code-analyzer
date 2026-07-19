import ast
from pathlib import Path


def file_to_module_parts(file_path: Path, root: Path | list[Path]) -> list[str]:
    """Convert a file path to its dotted module parts, relative to whichever
    source root actually contains it.
    root/utils/services/user_service.py -> ["utils", "services", "user_service"]
    root/utils/services/__init__.py     -> ["utils", "services"]
    """
    roots = [root] if isinstance(root, Path) else root
    matching_root = next((r for r in roots if file_path.is_relative_to(r)), roots[-1])
    rel = file_path.relative_to(matching_root)
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return parts


def get_source_roots(project_root: Path) -> list[Path]:
    """Determine the directories that top-level import statements resolve
    against, supporting both flat layouts (packages directly under the
    project root) and src-layout (packages under <root>/src).

    Order matters: src/ is checked first when present, since src-layout
    projects intentionally keep the root itself free of importable
    packages (avoids "editable install shadowing" ambiguity). The project
    root is always included as a fallback so flat-layout projects keep
    working unchanged.
    """
    roots = []
    src_dir = project_root / "src"
    if src_dir.is_dir():
        roots.append(src_dir)
    roots.append(project_root)
    return roots


def _resolve_module_to_file_in_root(module_parts: list[str], root: Path) -> Path | None:
    if not module_parts:
        return None
    base = root.joinpath(*module_parts)
    candidate_file = base.with_suffix(".py")
    candidate_pkg = base / "__init__.py"
    if candidate_file.is_file():
        return candidate_file
    if candidate_pkg.is_file():
        return candidate_pkg
    # PEP 420 namespace package: a directory with no __init__.py is still
    # a valid, importable package as long as it exists and contains
    # something. We point at the directory itself rather than a file;
    # callers that read file contents (e.g. get_top_level_names) must
    # handle a directory target gracefully.
    if base.is_dir():
        return base
    return None


def resolve_module_to_file(
    module_parts: list[str], root: Path | list[Path]
) -> Path | None:
    """Given dotted module parts (e.g. ["utils","directory","lookup"]),
    find the actual file under one of the source roots: either
    module_parts.py, module_parts/__init__.py, or (namespace package)
    module_parts/ as a bare directory.

    `root` may be a single Path (legacy call sites, flat layout) or a
    list of Paths as returned by get_source_roots (checked in order,
    first match wins — matters for src-layout precedence).
    """
    roots = [root] if isinstance(root, Path) else root
    for r in roots:
        found = _resolve_module_to_file_in_root(module_parts, r)
        if found:
            return found
    return None


def resolve_relative(
    current_module_parts: list[str], level: int, module: str | None
) -> list[str]:
    """Resolve a relative import's dotted parts into an absolute module path.

    current_module_parts: dotted parts of the FILE doing the importing
                           (e.g. ["utils","services","user_service"])
    level: number of leading dots (node.level from ast.ImportFrom)
    module: the part after the dots, e.g. "sibling" in "from .sibling import x"
            (None for bare "from . import x")

    Relative imports resolve from the PACKAGE containing the importing file,
    so we drop the importing file's own module name first, then go up
    (level - 1) additional levels.
    """
    package_parts = current_module_parts[:-1]
    up_levels = level - 1
    if up_levels > 0:
        package_parts = (
            package_parts[:-up_levels] if up_levels <= len(package_parts) else []
        )
    if module:
        return package_parts + module.split(".")
    return package_parts


def get_top_level_names(file_path: Path) -> tuple[set[str], list[str] | None]:
    """Parse `file_path` and return (top_level_names, all_list).

    top_level_names: every name bound directly at module scope — function
    defs, class defs, assignment targets, and names brought in via
    top-level import/import-from (since those are re-exportable too).

    all_list: the literal contents of `__all__` if the module defines one
    as a list/tuple of string constants, else None. Callers should treat
    `__all__` (when present) as the authoritative export surface.

    Used to verify `name_inside_module` guesses instead of assuming any
    name-inside-module import is valid just because the module file exists,
    and to make wildcard (`from x import *`) resolution `__all__`-aware.
    """
    if file_path.is_dir():
        # Namespace package (PEP 420): no single file to introspect for
        # top-level names. Treat as opaque — callers fall back to
        # "resolved but names unverifiable" rather than failing.
        return set(), None
    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(file_path))
    except (OSError, SyntaxError):
        return set(), None

    names: set[str] = set()
    all_list: list[str] | None = None

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
                    if target.id == "__all__" and isinstance(
                        node.value, (ast.List, ast.Tuple)
                    ):
                        all_list = [
                            elt.value
                            for elt in node.value.elts
                            if isinstance(elt, ast.Constant)
                            and isinstance(elt.value, str)
                        ]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                if bound != "*":
                    names.add(bound)

    return names, all_list


def resolve_import(alias: ast.alias, root: Path) -> dict:
    """Rule for: import x.y.z [as alias]"""
    module_parts = alias.name.split(".")
    target = resolve_module_to_file(module_parts, root)
    entry = {"kind": "import", "raw": alias.name, "alias": alias.asname}
    if target:
        entry["resolved_file"] = str(target)
    else:
        entry["reason"] = "stdlib or third-party (not found in project)"
    return entry


def resolve_import_from(
    alias: ast.alias,
    module: str | None,
    level: int,
    current_module_parts: list[str],
    root: Path,
) -> dict:
    """Rule for: from x.y import z / from . import z / from .sibling import z / from x import *

    Handles the submodule-vs-name-inside-module ambiguity by checking the
    filesystem for both possibilities, and wildcard imports by resolving
    the source module itself.
    """
    name = alias.name

    if level == 0:
        base_parts = module.split(".") if module else []
    else:
        base_parts = resolve_relative(current_module_parts, level, module)

    entry = {
        "kind": "from_import",
        "raw": f"{'.' * level}{module or ''}",
        "imported_name": name,
        "alias": alias.asname,
    }

    if name == "*":
        target = resolve_module_to_file(base_parts, root)
        if target:
            entry["resolved_file"] = str(target)
            top_level_names, all_list = get_top_level_names(target)
            if all_list is not None:
                entry["exported_names"] = all_list
                entry["note"] = (
                    "wildcard import: only names listed in __all__ are pulled in"
                )
            else:
                entry["exported_names"] = sorted(
                    n for n in top_level_names if not n.startswith("_")
                )
                entry["note"] = (
                    "wildcard import: module has no __all__, so all public "
                    "(non-underscore) top-level names are pulled in"
                )
        else:
            entry["reason"] = (
                "wildcard target not found in project (stdlib/third-party)"
            )
        return entry

    # Try: is `name` a submodule of base_parts? (base_parts/name.py)
    submodule_target = resolve_module_to_file(base_parts + [name], root)
    if submodule_target:
        entry["resolved_file"] = str(submodule_target)
        entry["resolution"] = "submodule"
        return entry

    # Fallback: `name` is a symbol defined inside base_parts' module/package
    package_target = resolve_module_to_file(base_parts, root)
    if package_target:
        if package_target.is_dir():
            # Namespace package: no file to introspect for names, so we
            # can't verify — resolve optimistically rather than falsely
            # rejecting a name that may well be defined in a submodule.
            entry["resolved_file"] = str(package_target)
            entry["resolution"] = "name_inside_module"
            entry["note"] = "target is a namespace package; name not verified"
            return entry
        top_level_names, all_list = get_top_level_names(package_target)
        exported = set(all_list) if all_list is not None else top_level_names
        if name in exported:
            entry["resolved_file"] = str(package_target)
            entry["resolution"] = "name_inside_module"
            return entry
        entry["reason"] = (
            f"'{name}' not found among top-level names of "
            f"{package_target} (checked __all__ if present, else module body)"
        )
        return entry

    entry["reason"] = "not found in project (stdlib/third-party)"
    return entry


def _extract_callable_ref(node: ast.expr) -> tuple[str | None, str]:
    """Best-effort extraction of a callable reference's bound name and a
    human-readable dotted representation, from a Name or Attribute node.
    Returns (bound_name, repr_string). bound_name is None if the argument
    isn't a simple name/attribute chain (e.g. a lambda, call result, or
    other expression) — those aren't statically resolvable at this level.
    """
    if isinstance(node, ast.Name):
        return node.id, node.id
    if isinstance(node, ast.Attribute):
        parts = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            parts.reverse()
            return node.attr, ".".join(parts)
        return None, ast.dump(node)[:80]
    return None, ast.dump(node)[:80]


def _resolve_callable_ref(
    dep_name: str | None,
    dep_repr: str,
    kind: str,
    line: int,
    import_map: dict,
    local_defs: set,
    current_file: str,
) -> dict:
    """Shared resolution logic for Depends(...) and add_task(...): trace
    the referenced callable back to either a name imported into this file
    (via import_map) or a function/class defined at this file's own top
    level (local_defs). This is intentionally file-local — it is NOT a
    real cross-file function call graph (that's TODO's pycg/jarviscg
    integration); it only tells you which FILE the dependency likely
    lives in, not whether the call graph edge itself is correct.
    """
    entry = {"kind": kind, "line": line, "raw": dep_repr}
    if dep_name is None:
        entry["reason"] = (
            "argument is not a simple name/attribute reference "
            "(e.g. a lambda or call expression) — cannot statically resolve"
        )
        return entry
    imported = import_map.get(dep_name)
    if imported and imported.get("resolved_file"):
        entry["resolved_file"] = imported["resolved_file"]
        entry["resolution"] = "imported_name"
        return entry
    if dep_name in local_defs:
        entry["resolved_file"] = current_file
        entry["resolution"] = "same_file"
        return entry
    entry["reason"] = (
        f"'{dep_name}' not found among this file's imports or " "top-level definitions"
    )
    return entry


def resolve_fastapi_dependency(
    node: ast.Call, import_map: dict, local_defs: set, current_file: str
) -> dict | None:
    """Rule for: Depends(dependency_callable) — FastAPI-style dependency
    injection, typically used as a parameter default:
    `def endpoint(db = Depends(get_db)): ...`

    Matches bare `Depends(...)` and `fastapi.Depends(...)`. Returns None
    if the call isn't a Depends(...) call at all.
    """
    func = node.func
    is_depends = (isinstance(func, ast.Name) and func.id == "Depends") or (
        isinstance(func, ast.Attribute) and func.attr == "Depends"
    )
    if not is_depends:
        return None
    if not node.args:
        return {
            "kind": "fastapi_dependency",
            "line": node.lineno,
            "raw": "Depends()",
            "reason": "no dependency callable argument",
        }
    dep_name, dep_repr = _extract_callable_ref(node.args[0])
    return _resolve_callable_ref(
        dep_name,
        dep_repr,
        "fastapi_dependency",
        node.lineno,
        import_map,
        local_defs,
        current_file,
    )


def resolve_background_task(
    node: ast.Call, import_map: dict, local_defs: set, current_file: str
) -> dict | None:
    """Rule for: background_tasks.add_task(callable, ...) registrations.
    Matches any `<expr>.add_task(...)` call — the receiver isn't checked
    against a known BackgroundTasks type (that would need real type
    inference), so this can over-match a same-named method on an
    unrelated class. Flagged via "kind" so callers can filter/verify.
    Returns None if the call isn't an add_task(...) call at all.
    """
    func = node.func
    is_add_task = isinstance(func, ast.Attribute) and func.attr == "add_task"
    if not is_add_task:
        return None
    if not node.args:
        return {
            "kind": "background_task",
            "line": node.lineno,
            "raw": "add_task()",
            "reason": "no callable argument",
        }
    dep_name, dep_repr = _extract_callable_ref(node.args[0])
    return _resolve_callable_ref(
        dep_name,
        dep_repr,
        "background_task",
        node.lineno,
        import_map,
        local_defs,
        current_file,
    )


def resolve_dynamic_call(node: ast.Call) -> dict | None:
    """Rule for: importlib.import_module("x.y.z") / __import__("x.y.z")

    Returns None if the call isn't a dynamic-import call at all.
    Target is a runtime value, so this is always flagged unresolved.
    """
    func = node.func
    is_dynamic = (isinstance(func, ast.Name) and func.id == "__import__") or (
        isinstance(func, ast.Attribute) and func.attr == "import_module"
    )
    if not is_dynamic:
        return None

    arg_repr = None
    if node.args and isinstance(node.args[0], ast.Constant):
        arg_repr = node.args[0].value

    return {
        "kind": "dynamic_import",
        "line": node.lineno,
        "raw": arg_repr
        if arg_repr
        else "<non-literal argument, cannot statically resolve>",
        "reason": "dynamic import: target is a runtime value, not statically resolvable",
    }
