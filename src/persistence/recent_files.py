"""Tracks the most recently opened/saved project files, persisted to a
small JSON file in the same ~/.clustersizer app-data directory already
used for the crash log - separate from any .clsz project file, since
this is app-level state, not project state.
"""

import json
from pathlib import Path

RECENT_FILES_PATH = Path.home() / ".clustersizer" / "recent_files.json"
MAX_RECENT_FILES = 5


def load_recent_files() -> list[str]:
    """Most-recently-used first. Missing/corrupt file -> empty list,
    never an error - this is a convenience feature, not project data."""
    try:
        data = json.loads(RECENT_FILES_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(p) for p in data]
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return []


def _save_recent_files(paths: list[str]) -> None:
    RECENT_FILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECENT_FILES_PATH.write_text(json.dumps(paths), encoding="utf-8")


def add_recent_file(path: str) -> None:
    """Moves path to the front if already present (re-opening/re-saving
    the same file bumps it back to most-recent, doesn't duplicate it),
    then trims to MAX_RECENT_FILES."""
    path = str(Path(path).resolve())
    paths = [p for p in load_recent_files() if p != path]
    paths.insert(0, path)
    _save_recent_files(paths[:MAX_RECENT_FILES])


def remove_recent_file(path: str) -> None:
    """For when a listed file no longer exists on disk - called after
    the user tries to open it and it fails, not proactively."""
    path = str(Path(path).resolve())
    paths = [p for p in load_recent_files() if p != path]
    _save_recent_files(paths)


def clear_recent_files() -> None:
    _save_recent_files([])
