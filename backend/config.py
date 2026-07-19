import re
import tomllib
from pathlib import Path

DEFAULTS = {
    "scan": {
        "exclude_patterns": [],
        "output_path": "result/module_graph.json",
        "cache_path": "result/.scan_cache.json",
    },
    "output": {
        "dot_path": "result/module_graph.dot",
        "include_unresolved_in_dot": False,
    },
}


def load_config(path: str = ".code-analyzer.toml") -> dict:
    """Returns a fully-populated config dict — DEFAULTS merged with
    whatever's in the file, so callers never need to guard against
    missing keys/sections. A missing or unparseable file just yields
    DEFAULTS (with a note logged to stderr for the unparseable case,
    since silently ignoring a typo'd config is worse than a working
    fallback plus a warning).
    """
    config = {section: dict(values) for section, values in DEFAULTS.items()}

    p = Path(path)
    if not p.exists():
        return config

    try:
        raw = tomllib.loads(p.read_text())
    except tomllib.TOMLDecodeError as e:
        import sys

        print(f"warning: could not parse {path} ({e}); using defaults", file=sys.stderr)
        return config

    for section, values in raw.items():
        if section not in config:
            config[section] = {}
        if isinstance(values, dict):
            config[section].update(values)

    return config


def build_exclude_regex(config: dict, base_regex: re.Pattern) -> re.Pattern:
    """Combine the built-in EXCLUDE_REGEX (constants/exclude.py) with any
    extra patterns from config's [scan].exclude_patterns, OR'd together.
    Falls back to the base regex unchanged if no extra patterns given.
    """
    extra = config.get("scan", {}).get("exclude_patterns", [])
    if not extra:
        return base_regex
    combined = base_regex.pattern
    if combined:
        combined = f"(?:{combined})|(?:{'|'.join(extra)})"
    else:
        combined = "|".join(extra)
    return re.compile(combined)
