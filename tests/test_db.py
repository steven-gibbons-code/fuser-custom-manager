import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))
from db import (init_db, upsert_songs, get_songs, mark_installed,
                mark_uninstalled, get_installed, get_setting, set_setting,
                get_songs_with_art_url, update_art_url, count_pending_art, ART_DIR)

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
    upsert_songs(conn, [SONG])  # Eligible + C = Definitive quality
    assert len(get_songs(conn, {"definitive_only": True})) == 1
    # Other-quality song should not appear
    not_def = {**SONG, "title": "Other", "link": "https://drive.google.com/file/d/xyz", "complete": "", "de_status": ""}
    upsert_songs(conn, [not_def])
    assert len(get_songs(conn, {"definitive_only": True})) == 1
    # Official-quality song should also appear in definitive_only filter
    official = {**SONG, "title": "Official", "link": "https://drive.google.com/file/d/off", "download_type": "DLC"}
    upsert_songs(conn, [official])
    assert len(get_songs(conn, {"definitive_only": True})) == 2

from db import derive_quality

@pytest.mark.parametrize("download_type,complete,de_status,notes,expected", [
    ("DLC",          "D", "",          "",           "Official"),
    ("Base Game",    "C", "",          "",           "Official"),
    ("Diamond Shop", "",  "",          "",           "Official"),
    ("Google Drive",  "D", "",          "",           "Definitive"),  # host label → not Official
    ("MediaFire",     "C", "Eligible",  "",           "Definitive"),  # host label → not Official
    ("https://drive.google.com/file/d/abc", "D", "", "", "Definitive"),
    ("",             "D", "",          "",           "Definitive"),
    ("",             "C", "Eligible",  "",           "Definitive"),
    ("",             "C", "",          "",           "Definitive"),
    ("",             "C", "",          "Wrong notes","Complete"),
    ("",             "C", "Not eligible", "",        "Complete"),
    ("",             "",  "",          "",           "Other"),
    ("",             "",  "Eligible",  "",           "Other"),
])
def test_derive_quality(download_type, complete, de_status, notes, expected):
    song = {
        "download_type": download_type, "complete": complete,
        "de_status": de_status, "complete_notes": notes,
    }
    assert derive_quality(song) == expected

def test_schema_has_new_columns(tmp_path):
    conn = init_db(tmp_path / "test.db")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(songs)").fetchall()}
    for col in ("disc1", "disc2", "disc3", "disc4", "download_type", "quality"):
        assert col in cols, f"Missing column: {col}"

def test_upsert_sets_quality(tmp_path):
    conn = init_db(tmp_path / "test.db")
    song = {**SONG, "download_type": "DLC", "disc1": "Drums", "disc2": "Vocals",
            "disc3": None, "disc4": None}
    upsert_songs(conn, [song])
    row = get_songs(conn, {})[0]
    assert row["quality"] == "Official"
    assert row["disc1"] == "Drums"
    assert row["disc2"] == "Vocals"

def test_upsert_quality_definitive(tmp_path):
    conn = init_db(tmp_path / "test.db")
    song = {**SONG, "download_type": "", "complete": "D"}
    upsert_songs(conn, [song])
    assert get_songs(conn, {})[0]["quality"] == "Definitive"

def test_upsert_quality_defaults_for_legacy_song(tmp_path):
    """upsert_songs handles songs without disc/download_type keys (backwards compat)."""
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG])  # SONG has no disc1–4 or download_type
    row = get_songs(conn, {})[0]
    assert row["quality"] in ("Official", "Definitive", "Complete", "Other")

def test_migrate_adds_columns_to_existing_schema(tmp_path):
    """Existing DB without quality/disc columns gets them added non-destructively."""
    import sqlite3 as _sql
    old_schema = """
    CREATE TABLE songs (
        id INTEGER PRIMARY KEY, source TEXT NOT NULL, artist TEXT, title TEXT,
        creator TEXT, genre TEXT, year INTEGER, bpm INTEGER, key TEXT,
        de_status TEXT, complete TEXT, complete_notes TEXT, stream_opt INTEGER DEFAULT 0,
        origin TEXT, link TEXT, link_host TEXT, last_seen TEXT, UNIQUE(source, link)
    );
    CREATE TABLE installed (
        id INTEGER PRIMARY KEY,
        song_id INTEGER UNIQUE REFERENCES songs(id) ON DELETE CASCADE,
        pak_path TEXT NOT NULL, sig_path TEXT, installed_at TEXT NOT NULL
    );
    """
    db_path = tmp_path / "old.db"
    old = _sql.connect(str(db_path))
    old.executescript(old_schema)
    old.close()
    conn = init_db(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(songs)").fetchall()}
    for col in ("disc1", "disc2", "disc3", "disc4", "download_type", "quality"):
        assert col in cols

from db import count_songs

def test_count_songs_total(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG])
    assert count_songs(conn, {}) == 1

def test_count_songs_search_filter(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG])
    assert count_songs(conn, {"search": "Daft"}) == 1
    assert count_songs(conn, {"search": "Nonexistent"}) == 0

def test_count_songs_installed_filter(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG])
    song = get_songs(conn, {})[0]
    assert count_songs(conn, {"installed": "installed"}) == 0
    assert count_songs(conn, {"installed": "not_installed"}) == 1
    mark_installed(conn, song["id"], r"C:\path\song.pak", r"C:\path\song.sig")
    assert count_songs(conn, {"installed": "installed"}) == 1
    assert count_songs(conn, {"installed": "not_installed"}) == 0

def test_get_songs_installed_filter(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG])
    song = get_songs(conn, {})[0]
    assert len(get_songs(conn, {"installed": "not_installed"})) == 1
    assert len(get_songs(conn, {"installed": "installed"})) == 0
    mark_installed(conn, song["id"], r"C:\path\song.pak", r"C:\path\song.sig")
    assert len(get_songs(conn, {"installed": "installed"})) == 1
    assert len(get_songs(conn, {"installed": "not_installed"})) == 0

def test_schema_has_submit_date(tmp_path):
    conn = init_db(tmp_path / "test.db")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(songs)").fetchall()}
    assert "submit_date" in cols

def test_upsert_stores_submit_date(tmp_path):
    conn = init_db(tmp_path / "test.db")
    song = {**SONG, "submit_date": "2024/05/01"}
    upsert_songs(conn, [song])
    row = get_songs(conn, {})[0]
    assert row["submit_date"] == "2024/05/01"

def test_get_songs_order_by_submit_date(tmp_path):
    conn = init_db(tmp_path / "test.db")
    older = {**SONG, "submit_date": "2023/01/01"}
    newer = {**SONG, "title": "Newer Song",
             "link": "https://drive.google.com/file/d/newer",
             "submit_date": "2024/06/01"}
    upsert_songs(conn, [older, newer])
    rows = get_songs(conn, {"order_by": "s.submit_date", "descending": True})
    assert rows[0]["title"] == "Newer Song"

def test_settings_table_created(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "settings" in tables

def test_get_set_setting(conn):
    set_setting(conn, "my_key", "my_value")
    assert get_setting(conn, "my_key") == "my_value"
    assert get_setting(conn, "nonexistent") is None

def test_init_db_seeds_default_install_path(tmp_path):
    c = init_db(tmp_path / "fresh.db")
    assert get_setting(c, "install_path") is not None

def test_init_db_does_not_overwrite_existing_setting(tmp_path):
    c = init_db(tmp_path / "fresh.db")
    set_setting(c, "install_path", r"C:\custom\path")
    c.close()
    c2 = init_db(tmp_path / "fresh.db")
    assert get_setting(c2, "install_path") == r"C:\custom\path"

def test_get_songs_no_limit_returns_all(tmp_path):
    conn = init_db(tmp_path / "test.db")
    songs = [
        {**SONG, "title": f"Song {i}", "link": f"https://drive.google.com/file/d/{i}"}
        for i in range(110)
    ]
    upsert_songs(conn, songs)
    rows = get_songs(conn, {}, limit=0)
    assert len(rows) == 110


def test_upsert_preserves_submit_date_when_null_incoming(tmp_path):
    """Re-fetching a song that now returns submit_date=None must not erase an existing date."""
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [{**SONG, "submit_date": "2024-03-15"}])
    # Re-upsert same song with submit_date missing (source didn't return it)
    upsert_songs(conn, [{**SONG, "submit_date": None}])
    row = get_songs(conn, {})[0]
    assert row["submit_date"] == "2024-03-15", (
        "existing submit_date was erased by a null incoming value"
    )


def test_upsert_updates_submit_date_when_new_date_provided(tmp_path):
    """A new non-null submit_date from the source should update the stored value."""
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [{**SONG, "submit_date": "2023-01-01"}])
    upsert_songs(conn, [{**SONG, "submit_date": "2024-06-15"}])
    row = get_songs(conn, {})[0]
    assert row["submit_date"] == "2024-06-15"


def test_art_url_column_exists_after_migration(tmp_path):
    conn = init_db(tmp_path / "test.db")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(songs)").fetchall()}
    assert "art_url" in cols

def test_upsert_preserves_art_url_on_resync(tmp_path):
    conn = init_db(tmp_path / "test.db")
    song = {**SONG, "art_url": "http://example.com/art.jpg"}
    upsert_songs(conn, [song])
    # Re-sync with art_url=None — existing URL must be preserved
    upsert_songs(conn, [{**SONG, "art_url": None}])
    row = conn.execute("SELECT art_url FROM songs").fetchone()
    assert row[0] == "http://example.com/art.jpg"

def test_upsert_updates_art_url_when_new_value_provided(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [{**SONG, "art_url": "http://example.com/old.jpg"}])
    upsert_songs(conn, [{**SONG, "art_url": "http://example.com/new.jpg"}])
    row = conn.execute("SELECT art_url FROM songs").fetchone()
    assert row[0] == "http://example.com/new.jpg"

def test_get_songs_with_art_url_returns_only_songs_with_url(tmp_path):
    conn = init_db(tmp_path / "test.db")
    s_with = {**SONG, "art_url": "http://img.com/a.jpg"}
    s_without = {**SONG, "title": "No Art", "link": "https://drive.google.com/file/d/xyz2",
                 "art_url": None}
    upsert_songs(conn, [s_with, s_without])
    result = get_songs_with_art_url(conn)
    assert len(result) == 1
    assert result[0]["art_url"] == "http://img.com/a.jpg"

def test_update_art_url_sets_value(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG])
    song_id = conn.execute("SELECT id FROM songs").fetchone()[0]
    update_art_url(conn, song_id, "http://img.com/cover.jpg")
    row = conn.execute("SELECT art_url FROM songs WHERE id = ?", (song_id,)).fetchone()
    assert row[0] == "http://img.com/cover.jpg"

def test_art_dir_is_under_fuser_manager():
    assert ART_DIR.parent.name == ".fuser_manager"
    assert ART_DIR.name == "art"

def test_count_pending_art_excludes_fsl_and_resolved(conn):
    upsert_songs(conn, [
        {**SONG, "source": "fucuco_main", "art_url": None,                          "title": "Pending", "link": "https://drive.google.com/file/d/pending1"},
        {**SONG, "source": "fucuco_main", "art_url": "http://example.com/a.jpg",    "title": "Resolved", "link": "https://drive.google.com/file/d/resolved1"},
        {**SONG, "source": "fusersoundlab", "art_url": None,                        "title": "FSL", "link": "https://drive.google.com/file/d/fsl1"},
    ])
    assert count_pending_art(conn) == 1  # only "Pending": fucuco + null art_url


def test_count_pending_art_returns_zero_when_all_resolved(conn):
    upsert_songs(conn, [{**SONG, "art_url": "http://example.com/art.jpg", "title": "Done"}])
    assert count_pending_art(conn) == 0
