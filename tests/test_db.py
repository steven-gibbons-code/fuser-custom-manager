import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))
from db import init_db, upsert_songs, get_songs, mark_installed, mark_uninstalled, get_installed

SONG = {
    "source": "fucuco_main", "artist": "Daft Punk", "title": "Get Lucky",
    "creator": "DJTest", "genre": "Pop", "year": 2013, "bpm": 116,
    "key": "A Minor", "de_status": "Eligible", "complete": "C",
    "complete_notes": "", "stream_opt": 1, "origin": None,
    "link": "https://drive.google.com/file/d/abc", "link_host": "gdrive",
    "last_seen": "2026-05-05",
}

@pytest.fixture
def conn(tmp_path):
    c = init_db(tmp_path / "test.db")
    yield c
    c.close()

def test_init_creates_tables(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "songs" in tables
    assert "installed" in tables

def test_upsert_inserts_new_song(conn):
    upsert_songs(conn, [SONG])
    rows = get_songs(conn, {})
    assert len(rows) == 1
    assert rows[0]["artist"] == "Daft Punk"

def test_upsert_updates_existing(conn):
    upsert_songs(conn, [SONG])
    updated = {**SONG, "bpm": 120}
    upsert_songs(conn, [updated])
    rows = get_songs(conn, {})
    assert len(rows) == 1
    assert rows[0]["bpm"] == 120

def test_mark_and_unmark_installed(conn):
    upsert_songs(conn, [SONG])
    song = get_songs(conn, {})[0]
    mark_installed(conn, song["id"],
                   r"C:\Fuser\Fuser\Content\Paks\custom_songs\Daft Punk\Get Lucky.pak",
                   r"C:\Fuser\Fuser\Content\Paks\custom_songs\Daft Punk\Get Lucky.sig")
    installed = get_installed(conn)
    assert len(installed) == 1
    assert installed[0]["pak_path"].endswith("Get Lucky.pak")
    mark_uninstalled(conn, song["id"])
    assert get_installed(conn) == []

@pytest.mark.parametrize("complete,de_status,notes,expected", [
    ("D", "",          "",           True),
    ("C", "Eligible",  "",           True),
    ("C", "",          "",           True),
    ("C", "",          "Some issue", False),
    ("C", "Not eligible", "",        False),
    ("",  "Eligible",  "",           False),
])
def test_is_definitive(conn, complete, de_status, notes, expected):
    song = {**SONG, "complete": complete, "de_status": de_status, "complete_notes": notes}
    upsert_songs(conn, [song])
    rows = get_songs(conn, {})
    assert bool(rows[0]["is_definitive"]) == expected

def test_get_songs_search_filter(conn):
    upsert_songs(conn, [SONG])
    assert len(get_songs(conn, {"search": "Daft"})) == 1
    assert len(get_songs(conn, {"search": "Nonexistent"})) == 0

def test_get_songs_definitive_only_filter(conn):
    upsert_songs(conn, [SONG])  # Eligible + C = definitive
    assert len(get_songs(conn, {"definitive_only": True})) == 1
    not_def = {**SONG, "title": "Other", "complete": "", "de_status": ""}
    upsert_songs(conn, [not_def])
    assert len(get_songs(conn, {"definitive_only": True})) == 1
