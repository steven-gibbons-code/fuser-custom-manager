import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))
from sources.fucuco import normalise_row, detect_link_host

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

def test_normalise_new_submissions_splits_artist_title():
    row = {
        "DE STATUS": "", "Complete": "C", "Stream-optimized": "0",
        "NEW SUBMISSIONS": "Taylor Swift - Anti-Hero",
        "BPM": "97", "Form Key": "F Major",
        "Link": "https://drive.google.com/file/d/def",
    }
    r = normalise_row(row, "fucuco_new")
    assert r["title"] == "Anti-Hero"
    assert r["artist"] == "Taylor Swift"

def test_normalise_skips_row_with_no_link():
    row = {"Artist": "No Link", "Title": "Song", "Link": ""}
    assert normalise_row(row, "fucuco_main") is None

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
