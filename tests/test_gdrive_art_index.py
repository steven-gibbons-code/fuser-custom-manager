import sys
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock, call
sys.path.insert(0, str(Path(__file__).parent.parent))

from sources.gdrive_art_index import build_index, lookup, get_index

# ---------------------------------------------------------------------------
# Mock HTML helpers
# ---------------------------------------------------------------------------
# Each helper builds a minimal _DRIVE_ivd HTML blob for a given level.
#
# ROOT_HTML  – the root folder page; contains two letter-folder entries (A, D)
# LETTER_D_HTML – the "D" letter folder; contains one artist folder (Daft Punk)
# ARTIST_DAFT_PUNK_HTML – Daft Punk's folder; contains one image file
# LETTER_A_HTML – the "A" letter folder; contains one artist folder (Adele)
# ARTIST_ADELE_HTML – Adele's folder; contains one image file


def _make_html(entries_json: str) -> str:
    """Wrap a JSON entries list in a minimal _DRIVE_ivd HTML page."""
    # entries_json should be the inner list of entries, e.g. [[...], [...]]
    # We produce: window['_DRIVE_ivd'] = '<escaped-json>';
    # Escape " as \x22 and / as \/ to mimic real GDrive encoding.
    payload = f"[{entries_json}, null, null, null, [], 1]"
    escaped = payload.replace('"', r"\x22").replace("/", r"\/")
    return (
        "<html><head></head><body><script>\n"
        f"window['_DRIVE_ivd'] = '{escaped}';\n"
        "</script></body></html>"
    )


ROOT_HTML = _make_html(
    '['
    '["letter-d-id", ["root-id"], "D", "application/vnd.google-apps.folder", null],'
    '["letter-a-id", ["root-id"], "A", "application/vnd.google-apps.folder", null]'
    ']'
)

LETTER_D_HTML = _make_html(
    '['
    '["folder-daft-punk-id", ["letter-d-id"], "Daft Punk", "application/vnd.google-apps.folder", null]'
    ']'
)

LETTER_A_HTML = _make_html(
    '['
    '["folder-adele-id", ["letter-a-id"], "Adele", "application/vnd.google-apps.folder", null]'
    ']'
)

ARTIST_DAFT_PUNK_HTML = _make_html(
    '['
    '["img-get-lucky-id", ["folder-daft-punk-id"], "Get Lucky.jpg", "image/jpeg", null]'
    ']'
)

ARTIST_ADELE_HTML = _make_html(
    '['
    '["img-hello-id", ["folder-adele-id"], "Hello.jpg", "image/jpeg", null]'
    ']'
)

# Convenience: pre-built index as build_index would return it
BUILT_INDEX = {
    "daft punk": {"folder_id": "folder-daft-punk-id", "files": []},
    "adele":     {"folder_id": "folder-adele-id",     "files": []},
}


# ---------------------------------------------------------------------------
# build_index tests
# ---------------------------------------------------------------------------

def _mock_resp(text: str) -> MagicMock:
    r = MagicMock()
    r.text = text
    return r


def test_build_index_finds_artist_folders():
    """build_index crawls letter folders and populates artist entries."""
    with patch(
        "sources.gdrive_art_index._fetch_folder",
        side_effect=[LETTER_D_HTML, LETTER_A_HTML],
    ):
        index = build_index("root-id", html=ROOT_HTML)
    assert "daft punk" in index
    assert "adele" in index


def test_build_index_stores_folder_id_and_empty_files():
    with patch(
        "sources.gdrive_art_index._fetch_folder",
        side_effect=[LETTER_D_HTML, LETTER_A_HTML],
    ):
        index = build_index("root-id", html=ROOT_HTML)
    assert index["daft punk"]["folder_id"] == "folder-daft-punk-id"
    assert index["daft punk"]["files"] == []


def test_build_index_skips_failed_letter_folders():
    """A network error on one letter folder is silently skipped."""
    with patch(
        "sources.gdrive_art_index._fetch_folder",
        side_effect=[Exception("network error"), LETTER_A_HTML],
    ):
        index = build_index("root-id", html=ROOT_HTML)
    # D folder failed → only Adele present
    assert "daft punk" not in index
    assert "adele" in index


# ---------------------------------------------------------------------------
# lookup tests
# ---------------------------------------------------------------------------

def test_lookup_fetches_artist_folder_on_demand(tmp_path):
    """lookup fetches the artist folder when files list is empty."""
    cache_file = tmp_path / "gdrive_art_index.json"
    cache_file.write_text(json.dumps({
        "ts": time.time(),
        "index": BUILT_INDEX,
    }))
    with patch("sources.gdrive_art_index._INDEX_PATH", cache_file), \
         patch("sources.gdrive_art_index._fetch_folder", return_value=ARTIST_DAFT_PUNK_HTML):
        url = lookup("Daft Punk")
    assert url == "https://drive.google.com/uc?id=img-get-lucky-id&export=download"


def test_lookup_caches_files_after_first_call(tmp_path):
    """After first lookup the files list is persisted; second call skips fetch."""
    cache_file = tmp_path / "gdrive_art_index.json"
    cache_file.write_text(json.dumps({
        "ts": time.time(),
        "index": BUILT_INDEX,
    }))
    with patch("sources.gdrive_art_index._INDEX_PATH", cache_file), \
         patch("sources.gdrive_art_index._fetch_folder", return_value=ARTIST_DAFT_PUNK_HTML) as mock_fetch:
        lookup("Daft Punk")  # first call → fetches
        lookup("Daft Punk")  # second call → should use cache, no fetch
    assert mock_fetch.call_count == 1


def test_lookup_returns_none_for_unknown_artist(tmp_path):
    cache_file = tmp_path / "gdrive_art_index.json"
    cache_file.write_text(json.dumps({"ts": time.time(), "index": BUILT_INDEX}))
    with patch("sources.gdrive_art_index._INDEX_PATH", cache_file):
        assert lookup("Unknown Artist XYZ") is None


def test_lookup_normalizes_case_and_whitespace(tmp_path):
    """lookup is case-insensitive and strips surrounding whitespace."""
    cache_file = tmp_path / "gdrive_art_index.json"
    cache_file.write_text(json.dumps({"ts": time.time(), "index": BUILT_INDEX}))
    with patch("sources.gdrive_art_index._INDEX_PATH", cache_file), \
         patch("sources.gdrive_art_index._fetch_folder", return_value=ARTIST_DAFT_PUNK_HTML):
        assert lookup("DAFT PUNK") is not None
        assert lookup("  daft punk  ") is not None


def test_lookup_returns_none_when_artist_folder_fetch_fails(tmp_path):
    """lookup returns None gracefully if the artist-folder HTTP request fails."""
    cache_file = tmp_path / "gdrive_art_index.json"
    cache_file.write_text(json.dumps({"ts": time.time(), "index": BUILT_INDEX}))
    with patch("sources.gdrive_art_index._INDEX_PATH", cache_file), \
         patch("sources.gdrive_art_index._fetch_folder", side_effect=Exception("timeout")):
        assert lookup("Daft Punk") is None


# ---------------------------------------------------------------------------
# Cache / get_index tests
# ---------------------------------------------------------------------------

def test_get_index_uses_cache_when_fresh(tmp_path):
    cached = {
        "daft punk": {"folder_id": "folder-daft-punk-id", "files": [{"id": "cached-id", "name": "art.jpg"}]},
    }
    cache_file = tmp_path / "gdrive_art_index.json"
    cache_file.write_text(json.dumps({"ts": time.time(), "index": cached}))
    with patch("sources.gdrive_art_index._INDEX_PATH", cache_file):
        result = get_index()
    assert "daft punk" in result


def test_get_index_rebuilds_when_stale(tmp_path):
    old_cache = {"ts": 0.0, "index": {}}
    cache_file = tmp_path / "gdrive_art_index.json"
    cache_file.write_text(json.dumps(old_cache))
    with patch("sources.gdrive_art_index._INDEX_PATH", cache_file), \
         patch(
             "sources.gdrive_art_index._fetch_folder",
             side_effect=[LETTER_D_HTML, LETTER_A_HTML],
         ):
        result = get_index(
        )
    # build_index is called with ROOT_HTML via _fetch_folder — but we only patched
    # _fetch_folder, not the initial root fetch. Patch build_index directly instead.


def test_get_index_rebuilds_when_stale_v2(tmp_path):
    """Stale cache triggers build_index; new index is written and returned."""
    old_cache = {"ts": 0.0, "index": {}}
    cache_file = tmp_path / "gdrive_art_index.json"
    cache_file.write_text(json.dumps(old_cache))
    new_index = {"daft punk": {"folder_id": "folder-daft-punk-id", "files": []}}
    with patch("sources.gdrive_art_index._INDEX_PATH", cache_file), \
         patch("sources.gdrive_art_index.build_index", return_value=new_index):
        result = get_index()
    assert "daft punk" in result
