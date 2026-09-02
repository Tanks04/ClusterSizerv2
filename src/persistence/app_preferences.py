"""App-level preferences (not project state) - currently just Advanced
Mode. Persisted to the same ~/.clustersizer app-data directory already
used for recent files and the crash log, kept in its own small JSON
file since it's a different kind of state (a UI preference, not a
project-history list).
"""

import json
from pathlib import Path

PREFERENCES_PATH = Path.home() / ".clustersizer" / "preferences.json"


def _load() -> dict:
    try:
        data = json.loads(PREFERENCES_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {}


def _save(data: dict) -> None:
    PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFERENCES_PATH.write_text(json.dumps(data), encoding="utf-8")


def load_advanced_mode() -> bool:
    """Default False - Clusters/Storage Pools/VLAN assignment are opt-in
    concepts most projects never need; this keeps the tables/dialogs
    they show up in uncluttered until explicitly turned on."""
    return bool(_load().get("advanced_mode", False))


def set_advanced_mode(enabled: bool) -> None:
    data = _load()
    data["advanced_mode"] = enabled
    _save(data)
