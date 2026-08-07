"""Save/load user-created ImportProfiles at the user level (not per-project)
so a mapping learned once works for every future project, on this machine."""

import json
from dataclasses import asdict
from pathlib import Path

from src.models.import_profile import ImportProfile, ColumnMapping

PROFILES_PATH = Path.home() / ".clustersizer" / "import_profiles.json"


def load_user_profiles() -> list[ImportProfile]:
    if not PROFILES_PATH.exists():
        return []
    try:
        raw = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    profiles = []
    for item in raw:
        mappings = [ColumnMapping(**m) for m in item.get("mappings", [])]
        profiles.append(ImportProfile(
            name=item.get("name", "Untitled"),
            header_row=item.get("header_row", 1),
            mappings=mappings,
            powered_on_value=item.get("powered_on_value", "Powered On"),
            skip_name_prefixes=item.get("skip_name_prefixes", []),
            built_in=False,
            notes=item.get("notes", ""),
        ))
    return profiles


def save_user_profiles(profiles: list[ImportProfile]) -> None:
    PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(p) for p in profiles if not p.built_in]
    PROFILES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def add_or_replace_profile(profile: ImportProfile) -> None:
    profiles = load_user_profiles()
    profiles = [p for p in profiles if p.name != profile.name]
    profiles.append(profile)
    save_user_profiles(profiles)


def delete_profile(name: str) -> None:
    profiles = [p for p in load_user_profiles() if p.name != name]
    save_user_profiles(profiles)
