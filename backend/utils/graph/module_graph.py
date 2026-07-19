import ast
import asyncio
import hashlib
import json
from pathlib import Path

from utils.rules.rules import (
    file_to_module_parts,
    resolve_import,
    resolve_import_from,
    resolve_dynamic_call,
    resolve_fastapi_dependency,
    resolve_background_task,
    get_source_roots,
)


class ImportVisitor(ast.NodeVisitor):
    """Walks a single file's AST, delegating every import pattern found
    to the matching rule in utils.rules.rules, and collecting results.

    Also builds a lightweight file-local name -> resolved_file map
    (import_map) and tracks this file's own top-level defs (local_defs)
    while it walks, so that Depends(...)/add_task(...) calls encountered
    later in the same file can be traced back to where their argument
    actually came from (see resolve_fastapi_dependency/resolve_background_task).
    This is a best-effort, file-local resolution — not a real cross-file
    function call graph (that's the pycg/jarviscg integration, still
    TODO).
    """

    def __init__(self, file_path: Path, roots: list[Path], local_defs: set):
        self.file_path = file_path
        self.roots = roots
        self.current_module_parts = file_to_module_parts(file_path, roots)
        self.resolved: list[dict] = []
        self.unresolved: list[dict] = []
        self.function_edges: list[dict] = []
        self.import_map: dict[str, dict] = {}
        self.local_defs = local_defs

    def _record_import_map(self, entry: dict, bound_name: str):
        if bound_name and bound_name != "*":
            self.import_map[bound_name] = {
                "resolved_file": entry.get("resolved_file"),
                "raw": entry.get("raw"),
            }

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            entry = resolve_import(alias, self.roots)
            entry["line"] = node.lineno
            (self.resolved if "resolved_file" in entry else self.unresolved).append(
                entry
            )
            bound = alias.asname or alias.name.split(".")[0]
            self._record_import_map(entry, bound)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            entry = resolve_import_from(
                alias,
                module=node.module,
                level=node.level,
                current_module_parts=self.current_module_parts,
                root=self.roots,
            )
            entry["line"] = node.lineno
            (self.resolved if "resolved_file" in entry else self.unresolved).append(
                entry
            )
            if alias.name == "*":
                for exported_name in entry.get("exported_names", []):
                    self.import_map[exported_name] = {
                        "resolved_file": entry.get("resolved_file"),
                        "raw": f"{entry.get('raw')}.{exported_name}",
                    }
            else:
                bound = alias.asname or alias.name
                self._record_import_map(entry, bound)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        dynamic = resolve_dynamic_call(node)
        if dynamic:
            self.unresolved.append(dynamic)

        current_file = str(self.file_path)
        dependency = resolve_fastapi_dependency(
            node, self.import_map, self.local_defs, current_file
        )
        if dependency:
            self.function_edges.append(dependency)

        background = resolve_background_task(
            node, self.import_map, self.local_defs, current_file
        )
        if background:
            self.function_edges.append(background)

        self.generic_visit(node)


def _top_level_defs(tree: ast.Module) -> set:
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def analyze_file(file_path: Path, root: Path | list[Path]) -> ImportVisitor:
    roots = [root] if isinstance(root, Path) else root
    source = file_path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source, filename=str(file_path))
    local_defs = _top_level_defs(tree)
    visitor = ImportVisitor(file_path, roots, local_defs)
    visitor.visit(tree)
    return visitor


def compute_file_hash(file_path: Path) -> str:
    """SHA-256 of a file's raw bytes. Used as each node's identity/version
    fingerprint so downstream consumers (incremental re-scan cache, or an
    LLM-context retrieval layer / RAG store) can tell whether a file's
    content actually changed since the last scan without re-parsing or
    re-diffing the whole file — just compare hashes.
    """
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def build_module_graph(root_dir: str, files: list[str]) -> dict:
    """
    root_dir: the project root passed to get_files_respecting_gitignore
    files:    the list it returned (relative or absolute paths to .py files)

    Schema:
      {
        "graph": {
          "<file>": {
            "hash": "<sha256>",
            "imports": [ <full per-import entry: kind, raw, imported_name,
                          alias, line, resolved_file, resolution/note> ]
          }, ...
        },
        "unresolved": [ <entry + "file"> ],
        "function_edges": [ <entry + "file">, kind is "fastapi_dependency"
                             or "background_task" ]
      }

    Note: "imports" holds the full per-import detail (not deduped target
    files) so that ambiguous *resolved* edges — e.g. name_inside_module
    guesses, wildcard imports — can still be confirmed/rejected by the
    human-in-the-loop review flow (overrides.py / review_cli.py), not
    just outright-unresolved ones.
    """
    root = Path(root_dir).resolve()
    roots = get_source_roots(root)
    graph = {}
    unresolved_all = []
    function_edges_all = []

    for f in files:
        file_path = Path(f)
        if not file_path.is_absolute():
            # `files` entries already come prefixed with root_dir (see
            # get_files_respecting_gitignore), so resolve relative to the
            # current working directory rather than joining onto `root`
            # again (that previously produced a doubled, nonexistent path).
            file_path = file_path.resolve()
        if file_path.suffix != ".py":
            continue  # skip README.md, pyproject.toml, etc.

        visitor = analyze_file(file_path, roots)
        graph[str(file_path)] = {
            "hash": compute_file_hash(file_path),
            "imports": visitor.resolved,
        }

        for u in visitor.unresolved:
            u["file"] = str(file_path)
            unresolved_all.append(u)

        for fe in visitor.function_edges:
            fe["file"] = str(file_path)
            function_edges_all.append(fe)

    return {
        "graph": graph,
        "unresolved": unresolved_all,
        "function_edges": function_edges_all,
    }


def save_module_graph(result: dict, output_path: str = "result/module_graph.json"):
    """Synchronous write — kept for callers that aren't in an event loop."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(result, f, indent=2)


async def save_module_graph_async(
    result: dict, output_path: str = "result/module_graph.json"
):
    """Non-blocking write: serializes to a string on the event loop (cheap),
    then offloads the actual disk write to a worker thread via
    asyncio.to_thread so it doesn't block other coroutines while the OS
    flushes to disk. Mirrors save_module_graph's behavior/signature.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2)

    def _write():
        with open(path, "w") as f:
            f.write(payload)

    await asyncio.to_thread(_write)
