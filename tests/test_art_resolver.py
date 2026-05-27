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
