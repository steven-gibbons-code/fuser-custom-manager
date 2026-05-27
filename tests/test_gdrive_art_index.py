import sys
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

from sources.gdrive_art_index import build_index, lookup, get_index

# MOCK_HTML uses the real _DRIVE_ivd format found in actual GDrive folder pages.
# The _DRIVE_ivd variable holds a JS single-quoted string with \x hex-escaped JSON.
# Structure: [entries, null, null, null, [], 1]
# Each entry: [id, [parent_id], name, mime_type, ...]
#
# This mock simulates a letter folder (e.g. "D") containing:
#  - Two artist sub-folders (Daft Punk, Adele) whose parent is "fake-folder-id"
#  - Two image files, each parented to the corresponding artist folder
MOCK_HTML = (
    "<html><head></head><body><script>\n"
    "window['_DRIVE_ivd'] = '"
    "[[["
    r"\x22folder-daft-punk-id\x22, [\x22fake-folder-id\x22], \x22Daft Punk\x22, "
    r"\x22application\/vnd.google-apps.folder\x22, null, null, null, null, null, null"
    "], ["
    r"\x22img-get-lucky-id\x22, [\x22folder-daft-punk-id\x22], \x22Get Lucky.jpg\x22, "
    r"\x22image\/jpeg\x22, null, null, null, null, null, null"
    "], ["
    r"\x22folder-adele-id\x22, [\x22fake-folder-id\x22], \x22Adele\x22, "
    r"\x22application\/vnd.google-apps.folder\x22, null, null, null, null, null, null"
    "], ["
    r"\x22img-hello-id\x22, [\x22folder-adele-id\x22], \x22Hello.jpg\x22, "
    r"\x22image\/jpeg\x22, null, null, null, null, null, null"
    "]], null, null, null, [], 1]"
    "';\n"
    "</script></body></html>"
)


def test_build_index_finds_artist_folders():
    index = build_index("fake-folder-id", html=MOCK_HTML)
    assert "daft punk" in index
    assert "adele" in index


def test_build_index_stores_image_file_id():
    index = build_index("fake-folder-id", html=MOCK_HTML)
    assert index["daft punk"]["files"][0]["id"] == "img-get-lucky-id"
    assert index["daft punk"]["files"][0]["name"] == "Get Lucky.jpg"


def test_lookup_returns_gdrive_url():
    index = build_index("fake-folder-id", html=MOCK_HTML)
    with patch("sources.gdrive_art_index._load_index", return_value=index):
        url = lookup("Daft Punk")
    assert url == "https://drive.google.com/uc?id=img-get-lucky-id&export=download"


def test_lookup_returns_none_for_unknown_artist():
    index = build_index("fake-folder-id", html=MOCK_HTML)
    with patch("sources.gdrive_art_index._load_index", return_value=index):
        assert lookup("Unknown Artist XYZ") is None


def test_lookup_normalizes_case_and_whitespace():
    index = build_index("fake-folder-id", html=MOCK_HTML)
    with patch("sources.gdrive_art_index._load_index", return_value=index):
        assert lookup("DAFT PUNK") is not None
        assert lookup("  daft punk  ") is not None


def test_get_index_uses_cache_when_fresh(tmp_path):
    cached = {"daft punk": {"files": [{"id": "cached-id", "name": "art.jpg"}]}}
    cache_file = tmp_path / "gdrive_art_index.json"
    cache_file.write_text(json.dumps({
        "ts": time.time(),
        "index": cached,
    }))
    with patch("sources.gdrive_art_index._INDEX_PATH", cache_file):
        result = get_index()
    assert "daft punk" in result


def test_get_index_rebuilds_when_stale(tmp_path):
    old_cache = {"ts": 0.0, "index": {}}
    cache_file = tmp_path / "gdrive_art_index.json"
    cache_file.write_text(json.dumps(old_cache))
    mock_resp = MagicMock()
    mock_resp.text = MOCK_HTML
    with patch("sources.gdrive_art_index._INDEX_PATH", cache_file), \
         patch("sources.gdrive_art_index.requests.get", return_value=mock_resp):
        result = get_index()
    assert "daft punk" in result
