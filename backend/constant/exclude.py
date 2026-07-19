import re

EXCLUDE_PATTERNS = [
    r"^__init__\.py$",
]
EXCLUDE_REGEX = re.compile("|".join(EXCLUDE_PATTERNS))
