"""Tests for the Recent Files persistence layer - a small JSON file in
~/.clustersizer, separate from any .clsz project. Uses monkeypatch to
redirect RECENT_FILES_PATH to a temp location so these tests never
touch the real user's actual recent-files list."""

import pytest

from src.persistence import recent_files


@pytest.fixture(autouse=True)
def isolated_recent_files_path(tmp_path, monkeypatch):
    monkeypatch.setattr(recent_files, "RECENT_FILES_PATH", tmp_path / "recent_files.json")


def test_empty_initially():
    assert recent_files.load_recent_files() == []


def test_add_recent_file_appears_at_front():
    recent_files.add_recent_file("/projects/a.clsz")
    result = recent_files.load_recent_files()
    assert len(result) == 1
    assert result[0].endswith("a.clsz")


def test_most_recently_added_is_first():
    recent_files.add_recent_file("/projects/a.clsz")
    recent_files.add_recent_file("/projects/b.clsz")
    recent_files.add_recent_file("/projects/c.clsz")

    result = recent_files.load_recent_files()

    assert [p.split("/")[-1] for p in result] == ["c.clsz", "b.clsz", "a.clsz"]


def test_readding_an_existing_entry_moves_it_to_front_without_duplicating():
    recent_files.add_recent_file("/projects/a.clsz")
    recent_files.add_recent_file("/projects/b.clsz")
    recent_files.add_recent_file("/projects/c.clsz")

    recent_files.add_recent_file("/projects/a.clsz")

    result = recent_files.load_recent_files()
    assert [p.split("/")[-1] for p in result] == ["a.clsz", "c.clsz", "b.clsz"]
    assert len(result) == 3


def test_list_is_capped_at_max_recent_files():
    for i in range(recent_files.MAX_RECENT_FILES + 5):
        recent_files.add_recent_file(f"/projects/p{i}.clsz")

    result = recent_files.load_recent_files()

    assert len(result) == recent_files.MAX_RECENT_FILES


def test_remove_recent_file():
    recent_files.add_recent_file("/projects/a.clsz")
    recent_files.add_recent_file("/projects/b.clsz")

    recent_files.remove_recent_file("/projects/a.clsz")

    result = recent_files.load_recent_files()
    assert len(result) == 1
    assert result[0].endswith("b.clsz")


def test_clear_recent_files():
    recent_files.add_recent_file("/projects/a.clsz")
    recent_files.add_recent_file("/projects/b.clsz")

    recent_files.clear_recent_files()

    assert recent_files.load_recent_files() == []


def test_corrupt_file_returns_empty_list_not_an_error(tmp_path, monkeypatch):
    path = tmp_path / "corrupt.json"
    path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(recent_files, "RECENT_FILES_PATH", path)

    assert recent_files.load_recent_files() == []
