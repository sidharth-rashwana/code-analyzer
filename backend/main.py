import argparse
import asyncio
from pathlib import Path

from utils.directory.lookup import get_files_respecting_gitignore, is_exist
from utils.graph.module_graph import save_module_graph_async
from utils.graph.function_graph import build_function_graph
from cache import build_module_graph_incremental
from config import load_config, build_exclude_regex
from constant.exclude import EXCLUDE_REGEX
from output_dot import save_dot
from diff import diff_files, format_diff_text
from llm_context import build_context_bundle


def _parse_args():
    parser = argparse.ArgumentParser(description="code-analyzer")
    parser.add_argument(
        "path",
        nargs="?",
        help="project directory to scan (omit for interactive prompt)",
    )
    parser.add_argument("--config", default=".code-analyzer.toml")
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="ignore the incremental scan cache and re-analyze every file",
    )
    parser.add_argument(
        "--dot",
        action="store_true",
        help="also write a Graphviz .dot file of the module graph",
    )
    parser.add_argument(
        "--diff",
        nargs=2,
        metavar=("OLD_JSON", "NEW_JSON"),
        help="compare two previously-saved module_graph.json snapshots and "
        "exit (doesn't scan anything)",
    )
    parser.add_argument(
        "--context",
        nargs="+",
        metavar="FUNCTION_ID",
        help="build an LLM-ready context bundle for one or more changed "
        "functions (ids look like '<file>::<qualname>', as printed by "
        "build_function_graph — run once without --context first if you "
        "don't know the exact id) and exit (doesn't do the normal module "
        "scan/save)",
    )
    parser.add_argument(
        "--context-max-tokens",
        type=int,
        default=8000,
        help="token budget for --context (default: 8000)",
    )
    parser.add_argument(
        "--context-output",
        default="result/context.md",
        help="where to write the --context bundle (default: result/context.md)",
    )
    parser.add_argument(
        "--no-git-info",
        action="store_true",
        help="skip git blame/last-commit info in --context bundles",
    )
    return parser.parse_args()


async def run_scan(path: str, config: dict, use_cache: bool = True):
    response = is_exist(path.strip())
    if response != "exists":
        print(f"{response}. Exiting ...")
        return None

    exclude_regex = build_exclude_regex(config, EXCLUDE_REGEX)
    files = get_files_respecting_gitignore(path, exclude_regex=exclude_regex)
    print(files)

    if use_cache:
        result, stats = build_module_graph_incremental(
            path, files, cache_path=config["scan"]["cache_path"]
        )
        print(f"scan stats: {stats}")
    else:
        from utils.graph.module_graph import build_module_graph

        result = build_module_graph(path, files)

    output_path = config["scan"]["output_path"]
    await save_module_graph_async(result, output_path)
    print(f"Saved to {output_path}")

    if config.get("_dot_requested"):
        dot_path = config["output"]["dot_path"]
        include_unresolved = config["output"]["include_unresolved_in_dot"]
        save_dot(result, path, dot_path, include_unresolved)
        print(f"Saved Graphviz DOT to {dot_path}")

    return result


def run_context(path: str, changed_functions: list[str], max_tokens: int,
                 output_path: str, include_git_info: bool):
    """Build the function graph fresh and assemble an LLM context bundle
    for `changed_functions`, then save it to `output_path`. Separate from
    run_scan() since it needs the function-level graph (build_function_graph),
    not the module-level one that the rest of main.py deals with.
    """
    response = is_exist(path.strip())
    if response != "exists":
        print(f"{response}. Exiting ...")
        return None

    files = get_files_respecting_gitignore(path)
    fg = build_function_graph(files, path)

    unknown = [fid for fid in changed_functions if fid not in fg]
    if unknown:
        print("Unknown function id(s), not found in this project's function graph:")
        for fid in unknown:
            print(f"  - {fid}")
        print(
            f"\n{len(fg)} known function id(s). A few examples:"
        )
        for fid in list(fg.keys())[:10]:
            print(f"  - {fid}")
        return None

    bundle = build_context_bundle(
        fg,
        changed_functions,
        max_tokens=max_tokens,
        repo_root=path,
        include_git_info=include_git_info,
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(bundle["bundle"])

    print(f"Saved context bundle to {output_path}")
    print(
        f"  full source: {len(bundle['included_full'])}, "
        f"stub only: {len(bundle['included_stub'])}, "
        f"omitted: {len(bundle['omitted'])}, "
        f"~{bundle['estimated_tokens']} tokens"
    )
    return bundle


async def main():
    args = _parse_args()

    if args.diff:
        old_path, new_path = args.diff
        print(format_diff_text(diff_files(old_path, new_path)))
        return

    config = load_config(args.config)
    config["_dot_requested"] = args.dot

    if args.context:
        path = args.path or input("Enter the path to directory : \t")
        run_context(
            path,
            args.context,
            args.context_max_tokens,
            args.context_output,
            include_git_info=not args.no_git_info,
        )
        return

    print("Hello from code-analyzer!")
    path = args.path or input("Enter the path to directory : \t")
    await run_scan(path, config, use_cache=not args.no_cache)


if __name__ == "__main__":
    asyncio.run(main())
