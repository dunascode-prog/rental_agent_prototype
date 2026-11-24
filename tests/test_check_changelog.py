"""Unit tests for the append-only CHANGELOG.md check (scripts/check_changelog.py)."""
from scripts.check_changelog import problems

OLD = "# Change log\n\n## 2026-11-24 · PR #1 · a\n- one\n"


def test_appended_entry_passes():
    assert problems(OLD, OLD + "\n## 2026-11-25 · PR #2 · b\n- two\n", other_files_changed=True) == []


def test_edited_line_fails():
    errors = problems(OLD, OLD.replace("- one", "- uno") + "\n## x\n", other_files_changed=True)
    assert errors and "line 4" in errors[0]


def test_deleted_line_fails():
    assert problems(OLD, "# Change log\n", other_files_changed=False)


def test_deleted_file_fails():
    assert problems(OLD, None, other_files_changed=True)


def test_change_without_entry_fails():
    assert problems(OLD, OLD, other_files_changed=True)
    assert problems(OLD, OLD + "- a stray line\n", other_files_changed=True)


def test_log_only_change_without_heading_passes():
    assert problems(OLD, OLD + "- a note\n", other_files_changed=False) == []


def test_new_file_passes_and_crlf_is_ignored():
    assert problems(None, OLD + "## first\n", other_files_changed=True) == []
    assert problems(OLD, OLD.replace("\n", "\r\n") + "## next\r\n", other_files_changed=True) == []
