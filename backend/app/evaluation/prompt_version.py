"""A stable identifier for "the prompts the pipeline is running with".

Every agent's system prompt lives in ``app/prompts/``. Hashing those files gives
each evaluation run a version it can be compared on: edit a prompt and the
version changes; leave them alone and it does not, whatever else changed.

Line endings are normalised first so a checkout on Windows and one on Linux
produce the same version for the same text.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def prompt_version(prompts_dir: Path = PROMPTS_DIR) -> str:
    digest = hashlib.sha256()
    for path in sorted(prompts_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(text.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:8]
