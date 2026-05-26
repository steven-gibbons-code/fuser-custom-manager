import sys
from pathlib import Path
from unittest.mock import patch
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))
from sources.fucuco import (
    normalise_row, detect_link_host, fetch_tab, _is_ref_error,
)

def test_normalise_full_db_row():
    row = {
        "DE STATUS": "Eligible", "Complete": "C", "Stream-optimized": "1",
        "Artist": "Daft Punk", "Title": "Get Lucky", "Creator": "DJTest",
        "Genre": "Pop", "Year": "2013", "BPM": "116", "Form Key": "A Minor",
        "Link": "https://drive.google.com/file/d/abc123",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["artist"] == "Daft Punk"
    assert r["title"] == "Get Lucky"
    assert r["bpm"] == 116
    assert r["key"] == "A Minor"
    assert r["complete"] == "C"
    assert r["de_status"] == "Eligible"
    assert r["link_host"] == "gdrive"
    assert r["stream_opt"] == 1
    assert r["source"] == "fucuco_main"

def test_normalise_vgm_row():
    row = {
        "Stream-optimized": "1", "Video Game Music Artist": "Nobuo Uematsu",
        "Title": "One-Winged Angel", "Creator": "FFfan",
        "Origin": "Final Fantasy VII", "Genre": "Classical",
        "Year": "1997", "BPM": "168", "Form Key": "E Minor",
        "Link": "https://drive.google.com/drive/folders/xyz",
    }
    r = normalise_row(row, "fucuco_vgm")
    assert r["artist"] == "Nobuo Uematsu"
    assert r["origin"] == "Final Fantasy VII"
    assert r["link_host"] == "gdrive"

def test_normalise_skips_row_with_no_link():
    row = {"Artist": "No Link", "Title": "Song", "Link": ""}
    assert normalise_row(row, "fucuco_main") is None

def test_normalise_skips_ref_error_link():
    """A row whose link is #REF! should be skipped."""
    row = {"Artist": "Test", "Title": "Song", "Link": "#REF!"}
    assert normalise_row(row, "fucuco_main") is None
    assert _is_ref_error("#REF!")
    assert _is_ref_error("#N/A")
    assert not _is_ref_error("https://valid.link")

def test_normalise_handles_ref_error_fields():
    """DE STATUS or Complete fields that are #REF! errors should become empty strings."""
    row = {
        "DE STATUS": "#REF!", "Complete": "#REF!", "Stream-optimized": "0",
        "Artist": "Test", "Title": "Song",
        "Link": "https://drive.google.com/file/d/abc",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["de_status"] == ""
    assert r["complete"] == ""

@pytest.mark.parametrize("url,expected", [
    ("https://drive.google.com/file/d/abc", "gdrive"),
    ("https://drive.google.com/drive/folders/xyz", "gdrive"),
    ("https://1drv.ms/u/abc", "onedrive"),
    ("https://www.mediafire.com/file/abc", "mediafire"),
    ("https://mega.nz/file/abc", "mega"),
    ("https://example.com/file", "other"),
    ("", "other"),
])
def test_detect_link_host(url, expected):
    assert detect_link_host(url) == expected


# ── Standard tab: search-row detection ──────────────────────────────────

CSV_WITH_SEARCH_ROW = """\
"","SEARCH","","","",""
"","type to search","","","",""
"","ARTIST","TITLE","LINK","STATE","SEASON"
"","Dua Lipa","Levitating","https://drive.google.com/file/d/abc","Active","S1"
"","The Weeknd","Blinding Lights","https://drive.google.com/file/d/def","","S2"
"""

CSV_WITHOUT_SEARCH_ROW = """\
"","ARTIST","TITLE","LINK","GENRE","BPM"
"","Dua Lipa","Levitating","https://drive.google.com/file/d/abc","Pop","103"
"","The Weeknd","Blinding Lights","https://drive.google.com/file/d/def","R&B","171"
"""

def test_fetch_tab_skips_search_row():
    """fetch_tab should skip the SEARCH filter row and find the real header."""
    with patch("sources.fucuco.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = CSV_WITH_SEARCH_ROW
        songs = fetch_tab("SOME TAB", "fucuco_main")
    assert len(songs) == 2
    assert songs[0]["artist"] == "Dua Lipa"
    assert songs[0]["title"] == "Levitating"
    assert songs[1]["artist"] == "The Weeknd"

def test_fetch_tab_without_search_row():
    """Tab without a search row should parse normally from row 0."""
    with patch("sources.fucuco.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = CSV_WITHOUT_SEARCH_ROW
        songs = fetch_tab("FULL DATABASE", "fucuco_main")
    assert len(songs) == 2
    assert songs[0]["artist"] == "Dua Lipa"
    assert songs[0]["bpm"] == 103

def test_normalise_includes_disc_fields():
    row = {
        "Artist": "Daft Punk", "Title": "Get Lucky", "Creator": "DJTest",
        "Disc 1 ": "Drums", "Disc 2 ": "Vocals", "Disc 3 ": "Sampler", "Disc 4 ": "",
        "Download": "Google Drive",
        "Link": "https://drive.google.com/file/d/abc",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["disc1"] == "Drums"
    assert r["disc2"] == "Vocals"
    assert r["disc3"] == "Sampler"
    assert r["disc4"] is None       # blank → None

def test_normalise_download_type_official():
    row = {
        "Artist": "Harmonix", "Title": "Base Song", "Creator": "Harmonix",
        "Download": "Base Game",
        "Link": "https://drive.google.com/file/d/xyz",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["download_type"] == "Base Game"

def test_normalise_download_type_url_passthrough():
    row = {
        "Artist": "A", "Title": "B", "Creator": "C",
        "Download": "https://drive.google.com/drive/folders/abc",
        "Link": "https://drive.google.com/file/d/def",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["download_type"] == "https://drive.google.com/drive/folders/abc"

def test_normalise_download_type_missing():
    row = {
        "Artist": "A", "Title": "B", "Creator": "C",
        "Link": "https://drive.google.com/file/d/ghi",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["download_type"] is None

def test_normalise_includes_submit_date():
    row = {
        "Artist": "Daft Punk", "Title": "Get Lucky", "Creator": "DJTest",
        "Submit Date": "2023/05/01",
        "Link": "https://drive.google.com/file/d/abc",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["submit_date"] == "2023-05-01"

def test_normalise_submit_date_blank_is_none():
    row = {
        "Artist": "A", "Title": "B",
        "Link": "https://drive.google.com/file/d/abc",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["submit_date"] is None

