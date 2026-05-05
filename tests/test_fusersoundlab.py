import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from sources.fusersoundlab import parse_html

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
