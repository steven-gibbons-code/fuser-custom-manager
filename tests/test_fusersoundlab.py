import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from sources.fusersoundlab import parse_html, parse_playlist_json

FIXTURE_HTML = """
<html><body>
<div class="track-item">
  <span class="track-title">Levitating</span>
  <span class="track-artist">Dua Lipa</span>
  <span class="track-bpm">103 BPM</span>
  <span class="track-key">G Major</span>
  <a class="download-link" href="https://drive.google.com/drive/folders/abc123">Download</a>
</div>
<div class="track-item">
  <span class="track-title">Blinding Lights</span>
  <span class="track-artist">The Weeknd</span>
  <span class="track-bpm">171 BPM</span>
  <span class="track-key">F Minor</span>
  <a class="download-link" href="https://drive.google.com/drive/folders/def456">Download</a>
</div>
</body></html>
"""

def test_parse_returns_two_songs():
    assert len(parse_html(FIXTURE_HTML)) == 2

def test_parse_fields():
    songs = parse_html(FIXTURE_HTML)
    s = songs[0]
    assert s["title"] == "Levitating"
    assert s["artist"] == "Dua Lipa"
    assert s["bpm"] == 103
    assert s["key"] == "G Major"
    assert s["link_host"] == "gdrive"
    assert s["source"] == "fusersoundlab"

def test_parse_skips_entry_without_link():
    html = '<div class="track-item"><span class="track-title">No Link</span></div>'
    assert parse_html(html) == []


# ── JSON API parser ──────────────────────────────────────────────────────────

FIXTURE_JSON = {
    "tracks": [
        {
            "id": 1, "track_title": "Levitating", "track_artist": "Dua Lipa",
            "has_song_store": True,
            "song_store_list": [{"store-icon": "fas fa-download", "store-name": "Download",
                                  "store-link": "https://drive.google.com/drive/folders/abc123"}],
            "description": False,
        },
        {
            "id": 2, "track_title": "No Download", "track_artist": "Artist",
            "has_song_store": False,
            "song_store_list": False,
            "description": False,
        },
        {
            "id": 3, "track_title": "Blinding Lights", "track_artist": "The Weeknd",
            "has_song_store": True,
            "song_store_list": [{"store-name": "Download",
                                  "store-link": "https://drive.google.com/drive/folders/def456"}],
            "description": False,
        },
    ]
}

FIXTURE_JSON_WITH_ART = {
    "tracks": [
        {
            "id": 1, "track_title": "Levitating", "track_artist": "Dua Lipa",
            "has_song_store": True,
            "song_store_list": [{"store-link": "https://drive.google.com/drive/folders/abc123"}],
            "poster": "https://fusersoundlab.com/wp-content/uploads/levitating.jpg",
            "optional_poster": "",
        },
        {
            "id": 2, "track_title": "Blinding Lights", "track_artist": "The Weeknd",
            "has_song_store": True,
            "song_store_list": [{"store-link": "https://drive.google.com/drive/folders/def456"}],
            "poster": "",
            "optional_poster": "https://fusersoundlab.com/wp-content/uploads/blinding.jpg",
        },
        {
            "id": 3, "track_title": "No Art", "track_artist": "Artist",
            "has_song_store": True,
            "song_store_list": [{"store-link": "https://drive.google.com/drive/folders/ghi789"}],
            "poster": "",
            "optional_poster": "",
        },
    ]
}

def test_parse_playlist_json_returns_two_songs():
    songs = parse_playlist_json(FIXTURE_JSON)
    assert len(songs) == 2  # has_song_store=False track is skipped

def test_parse_playlist_json_fields():
    songs = parse_playlist_json(FIXTURE_JSON)
    s = songs[0]
    assert s["title"] == "Levitating"
    assert s["artist"] == "Dua Lipa"
    assert s["link"] == "https://drive.google.com/drive/folders/abc123"
    assert s["link_host"] == "gdrive"
    assert s["source"] == "fusersoundlab"

def test_parse_playlist_json_skips_no_store_link():
    data = {"tracks": [{"id": 1, "track_title": "T", "track_artist": "A",
                         "has_song_store": True, "song_store_list": False}]}
    assert parse_playlist_json(data) == []

def test_parse_playlist_json_captures_poster_as_art_url():
    songs = parse_playlist_json(FIXTURE_JSON_WITH_ART)
    assert songs[0]["art_url"] == "https://fusersoundlab.com/wp-content/uploads/levitating.jpg"

def test_parse_playlist_json_falls_back_to_optional_poster():
    songs = parse_playlist_json(FIXTURE_JSON_WITH_ART)
    assert songs[1]["art_url"] == "https://fusersoundlab.com/wp-content/uploads/blinding.jpg"

def test_parse_playlist_json_art_url_none_when_no_poster():
    songs = parse_playlist_json(FIXTURE_JSON_WITH_ART)
    assert songs[2]["art_url"] is None
