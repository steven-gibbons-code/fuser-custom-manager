import sys
from pathlib import Path
from unittest.mock import patch
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))
from sources.fucuco import (
    normalise_row, detect_link_host, fetch_tab, get_sheet_tab_url, _is_ref_error,
    _split_pack_songs, _is_pack_header_row, _fetch_pack_tab,
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


# ── Sheet tab URL helper ────────────────────────────────────────────────

def test_get_sheet_tab_url_known_source():
    url = get_sheet_tab_url("fucuco_main")
    assert url is not None
    assert "FULL+DATABASE" in url

def test_get_sheet_tab_url_new_submissions():
    url = get_sheet_tab_url("fucuco_new")
    assert url is not None
    assert "NEW+SUBMISSIONS" in url

def test_get_sheet_tab_url_unknown_source():
    assert get_sheet_tab_url("nonexistent") is None


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


# ── Pack tab: header detection and content parsing ─────────────────────

def test_is_pack_header_row_positive():
    row = ["Creator", "Title", "N°", "V", "Download", "Date", "Content"]
    assert _is_pack_header_row(row) is True

def test_is_pack_header_row_negative():
    row = ["", "SEARCH", "", "", "", ""]
    assert _is_pack_header_row(row) is False

def test_is_pack_header_row_partial():
    row = ["Creator", "Title", "Something", "", "Download"]
    assert _is_pack_header_row(row) is True

def test_split_pack_songs_dash():
    content = "Dua Lipa - Levitating\nThe Weeknd – Blinding Lights\nArtist — Title"
    songs = _split_pack_songs(content)
    assert len(songs) == 3
    assert songs[0] == ("Dua Lipa", "Levitating")
    assert songs[1] == ("The Weeknd", "Blinding Lights")
    assert songs[2] == ("Artist", "Title")

def test_split_pack_songs_no_dash():
    content = "Just a Title"
    songs = _split_pack_songs(content)
    assert len(songs) == 1
    assert songs[0] == ("", "Just a Title")

def test_split_pack_songs_empty():
    assert _split_pack_songs("") == []
    assert _split_pack_songs("  \n  ") == []

def test_fetch_pack_tab_success():
    """End-to-end: mock export CSV, verify songs are parsed from Content."""
    csv_data = (
        "Notes row, with some text,,,,,Highlights\r\n"
        "Creator,Title,N°,V,Download,Date,Content\r\n"
        'Blahaszi,Green Day 01,3,V1,Google Drive,2023/05/22,"Green Day - 21 Guns\r\n'
        'Green Day - Good Riddance"\r\n'
        'Heartbreak Rebel,LSD Pack,8,V1,Google Drive,2023/10/08,"LSD - Audio\r\n'
        'LSD - Genius"\r\n'
    )
    with patch("sources.fucuco.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = csv_data
        songs = _fetch_pack_tab()
    assert len(songs) == 4
    assert songs[0]["artist"] == "Green Day"
    assert songs[0]["title"] == "21 Guns"
    assert songs[0]["creator"] == "Blahaszi"
    assert songs[0]["source"] == "fucuco_packs"
    assert songs[0]["link"] == "fucuco_packs://Blahaszi/Green Day 01"
    assert songs[0]["link_host"] == "other"
    assert songs[0]["origin"] == "Google Drive"
    assert songs[0]["complete_notes"] == "Green Day 01"
    assert songs[1]["artist"] == "Green Day"
    assert songs[1]["title"] == "Good Riddance"
    assert songs[1]["link"] == "fucuco_packs://Blahaszi/Green Day 01"
    assert songs[2]["artist"] == "LSD"
    assert songs[2]["title"] == "Audio"
    assert songs[2]["link"] == "fucuco_packs://Heartbreak Rebel/LSD Pack"
    assert songs[2]["origin"] == "Google Drive"
    assert songs[2]["creator"] == "Heartbreak Rebel"
    # All pack songs have unique links (per-pack synthetic URI)
    links = {s["link"] for s in songs}
    assert len(links) == 2  # one per pack

def test_fetch_pack_tab_empty_content_skipped():
    """Rows with empty Content should be skipped."""
    csv_data = """\
Creator,Title,N°,V,Download,Date,Content
SomeCreator,Some Pack,2,V1,Google Drive,2024/01/01,
AnotherCreator,Another Pack,1,V1,,,
"""
    with patch("sources.fucuco.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = csv_data
        songs = _fetch_pack_tab()
    assert len(songs) == 0

def test_fetch_pack_tab_no_header():
    """No header row found -> empty result."""
    with patch("sources.fucuco.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "nothing useful here"
        songs = _fetch_pack_tab()
    assert len(songs) == 0