import re
from datetime import date

import requests
from bs4 import BeautifulSoup

from sources.fucuco import detect_link_host

FSL_URL = "https://fusersoundlab.com"


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
            "source":         "fusersoundlab",
            "artist":         artist,
            "title":          title,
            "creator":        "",
            "genre":          "",
            "year":           None,
            "bpm":            _bpm(bpm_el.get_text() if bpm_el else ""),
            "key":            key_el.get_text(strip=True) if key_el else "",
            "de_status":      "",
            "complete":       "",
            "complete_notes": "",
            "stream_opt":     0,
            "origin":         None,
            "link":           link,
            "link_host":      detect_link_host(link),
            "last_seen":      date.today().isoformat(),
        })
    return songs


def fetch_all() -> list[dict]:
    resp = requests.get(FSL_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return parse_html(resp.text)
