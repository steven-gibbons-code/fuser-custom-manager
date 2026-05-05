import ast
import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from sources.fucuco import detect_link_host

FSL_URL = "https://fusersoundlab.com"
FSL_PLAYLIST_URL = (
    "https://fusersoundlab.com/?load=playlist.json&title=&albums=&category="
    "&posts_not_in=&category_not_in=&author=&feed_title=&feed=&feed_img="
    "&el_widget_id=&artwork=&posts_per_pages=-1&all_category=1"
    "&single_playlist=&reverse_tracklist=&audio_meta_field="
    "&repeater_meta_field=&import_file=&rss_items=-1&rss_item_title="
    "&is_favorite=&is_recentlyplayed=&srp_order=date_DESC"
)

_EMPTY_SONG = {
    "source": "fusersoundlab", "artist": "", "title": "", "creator": "",
    "genre": "", "year": None, "bpm": None, "key": "", "de_status": "",
    "complete": "", "complete_notes": "", "stream_opt": 0, "origin": None,
    "disc1": None, "disc2": None, "disc3": None, "disc4": None,
    "download_type": None,
}


def _parse_store_link(raw) -> str | None:
    """Extract the first download URL from a song_store_list value."""
    if not raw or raw == "False":
        return None
    if isinstance(raw, list):
        stores = raw
    else:
        try:
            stores = ast.literal_eval(str(raw))
        except (ValueError, SyntaxError):
            return None
    for store in stores:
        link = (store.get("store-link") or "").strip()
        if link:
            return link
    return None


def parse_playlist_json(data: dict) -> list[dict]:
    """Parse the fusersoundlab playlist JSON API response."""
    songs = []
    for track in data.get("tracks", []):
        # has_song_store may be boolean True or string "True" depending on API version
        hs = track.get("has_song_store")
        if hs is not True and hs != "True":
            continue
        link = _parse_store_link(track.get("song_store_list"))
        if not link:
            continue
        title  = (track.get("track_title")  or "").strip()
        artist = (track.get("track_artist") or "").strip()
        if not title and not artist:
            continue
        songs.append({
            **_EMPTY_SONG,
            "artist":    artist,
            "title":     title,
            "link":      link,
            "link_host": detect_link_host(link),
            "last_seen": date.today().isoformat(),
        })
    return songs


# ── Legacy HTML parser — kept for unit tests ────────────────────────────────

def _bpm(text: str) -> int | None:
    m = re.search(r"(\d+)\s*BPM", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def parse_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    songs = []
    for item in soup.select(".track-item, [class*='track-row'], tr[data-link]"):
        link_tag = item.find("a", href=True)
        if not link_tag or not link_tag["href"].strip():
            continue
        link = link_tag["href"].strip()
        title_el  = item.select_one(".track-title,  [class*='title']")
        artist_el = item.select_one(".track-artist, [class*='artist']")
        bpm_el    = item.select_one(".track-bpm,    [class*='bpm']")
        key_el    = item.select_one(".track-key,    [class*='key']")
        title  = title_el.get_text(strip=True)  if title_el  else ""
        artist = artist_el.get_text(strip=True) if artist_el else ""
        if not title and not artist:
            continue
        songs.append({
            **_EMPTY_SONG,
            "artist":    artist,
            "title":     title,
            "bpm":       _bpm(bpm_el.get_text() if bpm_el else ""),
            "key":       key_el.get_text(strip=True) if key_el else "",
            "link":      link,
            "link_host": detect_link_host(link),
            "last_seen": date.today().isoformat(),
        })
    return songs


def fetch_all() -> list[dict]:
    resp = requests.get(FSL_PLAYLIST_URL, timeout=60,
                        headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return parse_playlist_json(resp.json())
