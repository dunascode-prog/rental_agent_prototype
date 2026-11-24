"""CI check: CHANGELOG.md is append-only, and every change appends an entry.

Usage: python scripts/check_changelog.py <base-sha> <head-sha>

Fails when:
- any line that existed in CHANGELOG.md at the merge base was edited or deleted, or
- files other than CHANGELOG.md changed and no new entry (a "## " heading) was appended.
"""
from __future__ import annotations

import subprocess
import sys

LOG = "CHANGELOG.md"
ZERO_SHA = "0" * 40


def problems(old: str | None, new: str | None, other_files_changed: bool) -> list[str]:
    """Pure check, kept separate from git so it can be unit-tested."""
    old = (old or "").replace("\r\n", "\n")
    new = (new or "").replace("\r\n", "\n")
    errors: list[str] = []
    if old and not new:
        return [f"{LOG} was deleted; it is append-only."]
    if not new.startswith(old):
        old_lines, new_lines = old.split("\n"), new.split("\n")
        first = next(
            (i for i, line in enumerate(old_lines) if i >= len(new_lines) or new_lines[i] != line),
            len(old_lines),
        )
        errors.append(
            f"{LOG} is append-only, but existing line {first + 1} was edited or removed. "
            "Add new entries at the end of the file instead."
        )
        return errors
    appended = new[len(old):]
    if other_files_changed and not any(line.startswith("## ") for line in appended.split("\n")):
        errors.append(
            f"Files changed without a new entry in {LOG}. Append a '## <date> - <PR or commit> - <author>' entry at the end."
        )
    return errors


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def _file_at(ref: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{LOG}"], capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout if result.returncode == 0 else None


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    base, head = argv[1], argv[2]
    if not base or base == ZERO_SHA:
        print("No base commit (new branch); nothing to compare.")
        return 0
    merge_base = _git("merge-base", base, head).strip()
    changed = [name for name in _git("diff", "--name-only", merge_base, head).split("\n") if name]
    if not changed:
        print("No changes.")
        return 0
    errors = problems(_file_at(merge_base), _file_at(head), any(name != LOG for name in changed))
    for error in errors:
        print(f"::error file={LOG}::{error}")
    if not errors:
        print(f"{LOG} OK: append-only and has an entry for this change.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
