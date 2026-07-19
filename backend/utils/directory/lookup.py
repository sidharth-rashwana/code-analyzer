from pathlib import Path
from typing import List, Literal

import pathspec

from constant import exclude


def is_exist(dir: str) -> Literal["exists", "incorrect-path"]:
    dir_path = Path(dir)
    if dir_path.is_dir():
        return "exists"
    return "incorrect-path"


def get_files_respecting_gitignore(root_dir, exclude_regex=None) -> List:
    root = Path(root_dir)
    gitignore = root / ".gitignore"
    spec = pathspec.PathSpec.from_lines(
        "gitwildmatch",
        gitignore.read_text().splitlines() if gitignore.exists() else [],
    )
    active_exclude_regex = exclude_regex or exclude.EXCLUDE_REGEX
    result = []
    for path in root.rglob("*"):
        if path.is_file() and not active_exclude_regex.match(path.name):
            rel = path.relative_to(root).as_posix()
            if not spec.match_file(rel):
                result.append(str(path))
    return result
