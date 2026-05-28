import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

from sources.art_resolver import musicbrainz_lookup

def _mock_responses(mb_json, caa_status=200, caa_url="https://archive.org/img/cover.jpg"):
    """Return a pair of mock response objects for MB then CAA."""
    mb_resp = MagicMock()
    mb_resp.status_code = 200
    mb_resp.json.return_value = mb_json

    caa_resp = MagicMock()
    caa_resp.status_code = caa_status
    caa_resp.url = caa_url

    return [mb_resp, caa_resp]

def test_musicbrainz_lookup_returns_image_url():
    mb_json = {"releases": [{"id": "abc-123"}]}
    responses = _mock_responses(mb_json)
    with patch("sources.art_resolver.requests.get", side_effect=responses), \
         patch("sources.art_resolver.time.sleep"):
        result = musicbrainz_lookup("Daft Punk", "Get Lucky")
    assert result == "https://archive.org/img/cover.jpg"

def test_musicbrainz_lookup_returns_none_when_no_releases():
    mb_json = {"releases": []}
    mb_resp = MagicMock()
    mb_resp.status_code = 200
    mb_resp.json.return_value = mb_json
    with patch("sources.art_resolver.requests.get", return_value=mb_resp), \
         patch("sources.art_resolver.time.sleep"):
        result = musicbrainz_lookup("Unknown Artist", "Unknown Track")
    assert result is None

def test_musicbrainz_lookup_returns_none_when_caa_404():
    mb_json = {"releases": [{"id": "abc-123"}]}
    responses = _mock_responses(mb_json, caa_status=404, caa_url="")
    with patch("sources.art_resolver.requests.get", side_effect=responses), \
         patch("sources.art_resolver.time.sleep"):
        result = musicbrainz_lookup("Daft Punk", "Get Lucky")
    assert result is None

def test_musicbrainz_lookup_returns_none_on_network_error():
    with patch("sources.art_resolver.requests.get", side_effect=Exception("timeout")), \
         patch("sources.art_resolver.time.sleep"):
        result = musicbrainz_lookup("Daft Punk", "Get Lucky")
    assert result is None

def test_musicbrainz_lookup_returns_none_when_mb_non_200():
    mb_resp = MagicMock()
    mb_resp.status_code = 503
    with patch("sources.art_resolver.requests.get", return_value=mb_resp), \
         patch("sources.art_resolver.time.sleep"):
        result = musicbrainz_lookup("Daft Punk", "Get Lucky")
    assert result is None


from db import init_db, upsert_songs
from sources.art_resolver import bulk_resolve

SONG_FUCUCO = {
    "source": "fucuco_main", "artist": "Daft Punk", "title": "Get Lucky",
    "creator": "", "genre": "", "year": 2013, "bpm": 116, "key": "",
    "de_status": "", "complete": "", "complete_notes": "", "stream_opt": 0,
    "origin": None, "disc1": None, "disc2": None, "disc3": None, "disc4": None,
    "download_type": None, "submit_date": None, "art_url": None,
    "link": "https://drive.google.com/file/d/abc", "link_host": "gdrive",
    "last_seen": "2026-05-27",
}

SONG_FSL_WITH_ART = {
    **SONG_FUCUCO,
    "source": "fusersoundlab",
    "link": "https://drive.google.com/file/d/fsl1",
    "art_url": "http://fsl.com/poster.jpg",
}

SONG_FSL_NO_ART = {
    **SONG_FUCUCO,
    "source": "fusersoundlab",
    "link": "https://drive.google.com/file/d/fsl2",
    "art_url": None,
}


def test_bulk_resolve_sets_art_url_for_fucuco_songs(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG_FUCUCO])
    song_id = conn.execute("SELECT id FROM songs").fetchone()[0]

    with patch("sources.art_resolver.musicbrainz_lookup", return_value="http://mb.com/art.jpg"), \
         patch("sources.art_resolver.time.sleep"):
        bulk_resolve(conn)

    row = conn.execute("SELECT art_url FROM songs WHERE id = ?", (song_id,)).fetchone()
    assert row[0] == "http://mb.com/art.jpg"


def test_bulk_resolve_skips_fsl_songs_with_existing_art(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG_FSL_WITH_ART])

    with patch("sources.art_resolver.musicbrainz_lookup") as mock_mb:
        bulk_resolve(conn)
        mock_mb.assert_not_called()

    row = conn.execute("SELECT art_url FROM songs").fetchone()
    assert row[0] == "http://fsl.com/poster.jpg"


def test_bulk_resolve_skips_fsl_songs_without_art(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG_FSL_NO_ART])

    with patch("sources.art_resolver.musicbrainz_lookup") as mock_mb:
        bulk_resolve(conn)
        mock_mb.assert_not_called()


def test_bulk_resolve_falls_back_to_gdrive(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG_FUCUCO])

    with patch("sources.art_resolver.musicbrainz_lookup", return_value=None), \
         patch("sources.art_resolver.gdrive_art_lookup", return_value="http://gdrive.com/art.jpg"), \
         patch("sources.art_resolver.time.sleep"):
        bulk_resolve(conn)

    row = conn.execute("SELECT art_url FROM songs").fetchone()
    assert row[0] == "http://gdrive.com/art.jpg"


def test_bulk_resolve_leaves_null_when_all_sources_fail(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG_FUCUCO])

    with patch("sources.art_resolver.musicbrainz_lookup", return_value=None), \
         patch("sources.art_resolver.gdrive_art_lookup", return_value=None), \
         patch("sources.art_resolver.time.sleep"):
        bulk_resolve(conn)

    row = conn.execute("SELECT art_url FROM songs").fetchone()
    assert row[0] is None


def test_mb_throttle_serializes_calls():
    import threading, time
    from sources.art_resolver import _mb_throttle
    import sources.art_resolver as art_resolver_mod

    # Reset state
    art_resolver_mod._mb_last_call = 0.0

    call_times = []

    def call():
        _mb_throttle()
        call_times.append(time.time())

    threads = [threading.Thread(target=call) for _ in range(3)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    call_times.sort()
    # Each successive call should be at least 0.9s after the previous
    assert call_times[1] - call_times[0] >= 0.9
    assert call_times[2] - call_times[1] >= 0.9
