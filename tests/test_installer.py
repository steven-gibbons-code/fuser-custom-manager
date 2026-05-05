import sys
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from installer import sanitise_artist, install_pairs, uninstall, scan_and_sync
from db import init_db, upsert_songs, get_songs, get_installed
from downloader import DownloadResult

BASE_SONG = {
    "source": "fucuco_main", "artist": "Daft Punk", "title": "Get Lucky",
    "creator": "", "genre": "", "year": 2013, "bpm": 116, "key": "A Minor",
    "de_status": "Eligible", "complete": "C", "complete_notes": "",
    "stream_opt": 1, "origin": None, "link": "x", "link_host": "gdrive",
    "last_seen": "2026-05-05",
}

@pytest.fixture
def conn(tmp_path):
    c = init_db(tmp_path / "test.db")
    yield c
    c.close()

def test_sanitise_strips_illegal_chars():
    assert sanitise_artist("AC/DC")         == "ACDC"
    assert sanitise_artist("Artist: Name")  == "Artist Name"
    assert sanitise_artist("  Spaced  ")    == "Spaced"
    assert sanitise_artist("Bad\\Slash")    == "BadSlash"

def test_install_moves_pak_and_sig(tmp_path, conn):
    upsert_songs(conn, [BASE_SONG])
    song = get_songs(conn, {})[0]
    staging = tmp_path / "staging"
    staging.mkdir()
    pak = staging / "song.pak"
    sig = staging / "song.sig"
    pak.write_text("")
    sig.write_text("")
    result = DownloadResult(status="ok", pairs=[(pak, sig)], error_msg=None, raw_url="x")
    install_root = tmp_path / "custom_songs"
    install_pairs(result, song["id"], song["artist"], install_root, conn)
    installed = get_installed(conn)
    assert len(installed) == 1
    assert Path(installed[0]["pak_path"]).exists()
    assert Path(installed[0]["sig_path"]).exists()

def test_uninstall_removes_files_and_empty_dir(tmp_path, conn):
    upsert_songs(conn, [BASE_SONG])
    song = get_songs(conn, {})[0]
    staging = tmp_path / "staging"
    staging.mkdir()
    pak = staging / "song.pak"
    sig = staging / "song.sig"
    pak.write_text("")
    sig.write_text("")
    result = DownloadResult(status="ok", pairs=[(pak, sig)], error_msg=None, raw_url="x")
    install_root = tmp_path / "custom_songs"
    install_pairs(result, song["id"], song["artist"], install_root, conn)
    uninstall(song["id"], install_root, conn)
    assert get_installed(conn) == []
    assert not (install_root / "Daft Punk").exists()

def test_scan_and_sync_picks_up_existing_files(tmp_path, conn):
    upsert_songs(conn, [BASE_SONG])
    install_root = tmp_path / "custom_songs"
    artist_dir = install_root / "Daft Punk"
    artist_dir.mkdir(parents=True)
    (artist_dir / "Get Lucky.pak").write_text("")
    (artist_dir / "Get Lucky.sig").write_text("")
    scan_and_sync(install_root, conn)
    assert len(get_installed(conn)) == 1
