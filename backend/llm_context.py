"""
llm_context.py

Turns a set of "changed" function ids (in the <file>::<qualname> form
produced by utils.graph.function_graph) into an actual context bundle
that can be pasted into an LLM prompt. Everything upstream of this
(module_graph, function_graph, bfs, cache) produces *data*; this is the
one piece that turns it into a prompt — the original goal per README.md.

Relevance/priority, most important first:
  1. the changed functions themselves        (always full source)
  2. their direct callers   (bfs.callers, depth=1)  — "what breaks"
  3. their direct callees   (bfs.callees, depth=1)  — "what it relies on"
  4. deeper callers, then deeper callees, by increasing depth

Trimming when max_tokens doesn't cover everything: an item that doesn't
fit at full source falls back to a signature-only stub
(extract_function_signature) rather than being dropped outright; only if
even the stub doesn't fit is it fully omitted (and still listed, so the
LLM knows what it's missing rather than silently not knowing).

Token counting is a rough ~4-chars/token heuristic, not a real
tokenizer — good enough to decide what to trim, not meant to be exact.

Git provenance (best-effort, off by a flag): last commit touching each
included file, plus `git blame`-derived authors for the function's own
line range, when repo_root is a git repository. Missing git info never
blocks bundle assembly — a file with no git history just gets no git
block.
"""

import subprocess
from pathlib import Path

from bfs import callers, callees
from utils.graph.function_graph import (
    extract_function_source,
    extract_function_signature,
    extract_function_line_range,
)


def _count_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _priority_order(
    function_graph: dict, changed_functions: list[str]
) -> list[tuple[str, str, int]]:
    """[(function_id, role, depth), ...] in priority order. role is
    "changed" | "caller" | "callee". A function reached via multiple
    paths/roles keeps only its single best entry (changed beats caller
    beats callee; within a role, lower depth wins).
    """
    changed_set = set(changed_functions)
    role_rank = {"changed": 0, "caller": 1, "callee": 2}
    best: dict[str, tuple[int, int, str]] = {}

    def consider(fid: str, role: str, depth: int):
        if fid in changed_set and role != "changed":
            return
        candidate = (role_rank[role], depth, role)
        current = best.get(fid)
        if current is None or candidate[:2] < current[:2]:
            best[fid] = candidate

    for fid in changed_functions:
        consider(fid, "changed", 0)

    for fid in changed_functions:
        if fid not in function_graph:
            continue
        for caller_id, depth in callers(function_graph, fid).items():
            consider(caller_id, "caller", depth)
        for callee_id, depth in callees(function_graph, fid).items():
            consider(callee_id, "callee", depth)

    ordered = sorted(best.items(), key=lambda kv: (kv[1][0], kv[1][1]))
    return [(fid, role, depth) for fid, (_, depth, role) in ordered]


def _run_git(args: list[str], repo_root: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _git_info(
    file_path: str,
    line_range: tuple[int, int] | None,
    repo_root: str,
) -> dict | None:
    """Best-effort git provenance for one function. Returns None entirely
    if this isn't a git repo, git isn't installed, or the file isn't
    tracked — a missing answer here shouldn't break context assembly.
    """
    last_commit = _run_git(
        ["log", "-1", "--format=%an|%ad|%s", "--date=short", "--", file_path],
        repo_root,
    )
    if last_commit is None:
        return None

    info: dict = {}
    if last_commit:
        parts = last_commit.split("|", 2)
        if len(parts) == 3:
            info["last_author"] = parts[0]
            info["last_commit_date"] = parts[1]
            info["last_commit_message"] = parts[2]

    if line_range:
        start_line, end_line = line_range
        blame = _run_git(
            ["blame", "-L", f"{start_line},{end_line}", "--porcelain", "--", file_path],
            repo_root,
        )
        if blame:
            authors = {
                line.split(" ", 1)[1]
                for line in blame.splitlines()
                if line.startswith("author ") and not line.startswith("author-mail")
            }
            if authors:
                info["blame_authors"] = sorted(authors)

    return info or None


def _format_git_block(info: dict | None) -> str:
    if not info:
        return ""
    bits = []
    if "last_author" in info:
        bits.append(
            f"last touched by {info['last_author']} "
            f"({info.get('last_commit_date', '?')}): "
            f"\"{info.get('last_commit_message', '')}\""
        )
    if "blame_authors" in info:
        bits.append(f"line authors: {', '.join(info['blame_authors'])}")
    if not bits:
        return ""
    return f"\n<!-- git: {' | '.join(bits)} -->\n"


def build_context_bundle(
    function_graph: dict,
    changed_functions: list[str],
    max_tokens: int = 8000,
    repo_root: str | None = None,
    include_git_info: bool = True,
) -> dict:
    """Assemble an LLM-ready context bundle for a set of changed
    functions.

    function_graph: output of utils.graph.function_graph.build_function_graph()
    changed_functions: function ids (<file>::<qualname>) in that graph

    Returns:
      {
        "bundle": "<the assembled text, ready to paste into a prompt>",
        "included_full": [function_id, ...],
        "included_stub": [function_id, ...],
        "omitted": [function_id, ...],
        "estimated_tokens": int,
      }
    """
    missing = [fid for fid in changed_functions if fid not in function_graph]
    if missing:
        raise ValueError(f"unknown function id(s), not in function_graph: {missing}")

    order = _priority_order(function_graph, changed_functions)

    included_full: list[str] = []
    included_stub: list[str] = []
    omitted: list[str] = []

    header = (
        f"# Context for change to: {', '.join(changed_functions)}\n\n"
        "Ordered by relevance: changed functions first, then direct "
        "callers (blast radius), then callees (dependencies), then "
        "deeper neighbors. Items marked [stub] show only the signature "
        "because the full body didn't fit the token budget.\n"
    )
    sections: list[str] = [header]
    budget = max_tokens - _count_tokens(header)

    for fid, role, depth in order:
        node = function_graph[fid]
        file_path = Path(node["file"])
        qualname = node["name"]
        label = f"## [{role}, depth={depth}] {fid}"

        line_range = None
        try:
            line_range = extract_function_line_range(file_path, qualname)
        except (OSError, SyntaxError):
            pass

        git_block = ""
        if include_git_info and repo_root:
            git_block = _format_git_block(
                _git_info(str(file_path), line_range, repo_root)
            )

        full_source = None
        try:
            full_source = extract_function_source(file_path, qualname)
        except (OSError, SyntaxError):
            pass

        if full_source is not None:
            block = f"{label}{git_block}\n```python\n{full_source}\n```\n"
            cost = _count_tokens(block)
            if cost <= budget:
                sections.append(block)
                included_full.append(fid)
                budget -= cost
                continue

        stub = None
        try:
            stub = extract_function_signature(file_path, qualname)
        except (OSError, SyntaxError):
            pass

        if stub is not None:
            block = f"{label} [stub]{git_block}\n```python\n{stub}\n```\n"
            cost = _count_tokens(block)
            if cost <= budget:
                sections.append(block)
                included_stub.append(fid)
                budget -= cost
                continue

        omitted.append(fid)

    if omitted:
        sections.append(
            "## Omitted (didn't fit token budget)\n"
            + "\n".join(f"- {f}" for f in omitted)
        )

    bundle = "\n".join(sections)
    return {
        "bundle": bundle,
        "included_full": included_full,
        "included_stub": included_stub,
        "omitted": omitted,
        "estimated_tokens": _count_tokens(bundle),
    }
