import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

from sources.art_resolver import itunes_lookup


def _make_itunes_resp(results):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"results": results}
    return resp


def test_itunes_lookup_returns_album_and_url():
    result = [{"collectionName": "Random Access Memories", "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/abc/100x100bb.jpg"}]
    with patch("sources.art_resolver.requests.get", return_value=_make_itunes_resp(result)), \
         patch("sources.art_resolver.time.sleep"):
        album, url = itunes_lookup("Daft Punk", "Get Lucky")
    assert album == "Random Access Memories"
    assert "600x600bb" in url


def test_itunes_lookup_returns_none_when_no_results():
    with patch("sources.art_resolver.requests.get", return_value=_make_itunes_resp([])), \
         patch("sources.art_resolver.time.sleep"):
        result = itunes_lookup("Unknown Artist", "Unknown Track")
    assert result is None


def test_itunes_lookup_returns_none_when_non_200():
    resp = MagicMock()
    resp.status_code = 503
    with patch("sources.art_resolver.requests.get", return_value=resp), \
         patch("sources.art_resolver.time.sleep"):
        result = itunes_lookup("Daft Punk", "Get Lucky")
    assert result is None


def test_itunes_lookup_returns_none_on_network_error():
    with patch("sources.art_resolver.requests.get", side_effect=Exception("timeout")), \
         patch("sources.art_resolver.time.sleep"):
        result = itunes_lookup("Daft Punk", "Get Lucky")
    assert result is None


def test_itunes_lookup_returns_none_when_missing_album():
    result = [{"artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/abc/100x100bb.jpg"}]
    with patch("sources.art_resolver.requests.get", return_value=_make_itunes_resp(result)), \
         patch("sources.art_resolver.time.sleep"):
        assert itunes_lookup("Daft Punk", "Get Lucky") is None


def test_itunes_lookup_returns_none_when_missing_artwork():
    result = [{"collectionName": "Random Access Memories"}]
    with patch("sources.art_resolver.requests.get", return_value=_make_itunes_resp(result)), \
         patch("sources.art_resolver.time.sleep"):
        assert itunes_lookup("Daft Punk", "Get Lucky") is None


def test_itunes_throttle_serializes_calls():
    import threading, time
    from sources.art_resolver import _itunes_throttle
    import sources.art_resolver as ar
    original = ar._ITUNES_LAST_CALL
    ar._ITUNES_LAST_CALL = 0.0
    try:
        call_times = []
        def call():
            _itunes_throttle()
            call_times.append(time.time())
        threads = [threading.Thread(target=call) for _ in range(3)]
        for t in threads: t.start()
        for t in threads: t.join()
        call_times.sort()
        assert call_times[1] - call_times[0] >= 0.3
        assert call_times[2] - call_times[1] >= 0.3
    finally:
        ar._ITUNES_LAST_CALL = original


# --- bulk_resolve tests ---
from db import init_db, upsert_songs
from sources.art_resolver import bulk_resolve

_SONG = {
    "source": "fucuco_main", "artist": "Daft Punk", "title": "Get Lucky",
    "creator": "", "genre": "", "year": 2013, "bpm": 116, "key": "",
    "de_status": "", "complete": "", "complete_notes": "", "stream_opt": 0,
    "origin": None, "disc1": None, "disc2": None, "disc3": None, "disc4": None,
    "download_type": None, "submit_date": None,
    "link": "https://drive.google.com/file/d/abc", "link_host": "gdrive",
    "last_seen": "2026-05-28",
}

_FSL_SONG = {
    **_SONG,
    "source": "fusersoundlab",
    "link": "https://fsl.com/1",
}


def test_bulk_resolve_sets_album_art_id_via_itunes(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [_SONG])
    song_id = conn.execute("SELECT id FROM songs").fetchone()[0]

    with patch("sources.art_resolver.itunes_lookup", return_value=("RAM", "http://itunes.com/art.jpg")), \
         patch("sources.art_resolver.requests.get") as mock_dl:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"FAKEIMAGE"
        mock_dl.return_value = mock_resp
        bulk_resolve(conn, art_dir=tmp_path / "art")

    row = conn.execute("SELECT album_art_id FROM songs WHERE id = ?", (song_id,)).fetchone()
    assert row[0] is not None
    art_row = conn.execute("SELECT album FROM album_art WHERE id = ?", (row[0],)).fetchone()
    assert art_row[0] == "RAM"


def test_bulk_resolve_skips_fsl_songs(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [_FSL_SONG])

    with patch("sources.art_resolver.itunes_lookup") as mock_itunes:
        bulk_resolve(conn, art_dir=tmp_path / "art")
        mock_itunes.assert_not_called()


def test_bulk_resolve_falls_back_to_gdrive(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [_SONG])
    song_id = conn.execute("SELECT id FROM songs").fetchone()[0]

    with patch("sources.art_resolver.itunes_lookup", return_value=None), \
         patch("sources.art_resolver.gdrive_art_lookup", return_value="http://gdrive.com/art.jpg"), \
         patch("sources.art_resolver.requests.get") as mock_dl:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"FAKEIMAGE"
        mock_dl.return_value = mock_resp
        bulk_resolve(conn, art_dir=tmp_path / "art")

    row = conn.execute("SELECT album_art_id FROM songs WHERE id = ?", (song_id,)).fetchone()
    assert row[0] is not None
    art_row = conn.execute("SELECT album FROM album_art WHERE id = ?", (row[0],)).fetchone()
    assert art_row[0] == "__artist__"


def test_bulk_resolve_leaves_null_when_all_sources_fail(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [_SONG])
    song_id = conn.execute("SELECT id FROM songs").fetchone()[0]

    with patch("sources.art_resolver.itunes_lookup", return_value=None), \
         patch("sources.art_resolver.gdrive_art_lookup", return_value=None):
        bulk_resolve(conn, art_dir=tmp_path / "art")

    row = conn.execute("SELECT album_art_id FROM songs WHERE id = ?", (song_id,)).fetchone()
    assert row[0] is None


def test_bulk_resolve_deduplicates_album_downloads(tmp_path):
    """Two songs on the same album should produce one album_art row and one file."""
    conn = init_db(tmp_path / "test.db")
    song_a = {**_SONG, "title": "Get Lucky"}
    song_b = {**_SONG, "title": "Lose Yourself to Dance", "link": "https://drive.google.com/file/d/xyz"}
    upsert_songs(conn, [song_a, song_b])

    download_count = [0]
    def fake_download(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"IMG"
        download_count[0] += 1
        return resp

    with patch("sources.art_resolver.itunes_lookup", return_value=("RAM", "http://itunes.com/art.jpg")), \
         patch("sources.art_resolver.requests.get", side_effect=fake_download):
        bulk_resolve(conn, art_dir=tmp_path / "art")

    # Only one download should have happened (file exists after first song)
    assert download_count[0] == 1
    # Both songs should point to the same album_art row
    rows = conn.execute("SELECT album_art_id FROM songs WHERE source='fucuco_main'").fetchall()
    ids = [r[0] for r in rows]
    assert ids[0] == ids[1]
