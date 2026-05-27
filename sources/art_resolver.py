import time
import sqlite3
import requests

from db import update_art_url
from sources.gdrive_art_index import lookup as gdrive_art_lookup

_MB_URL = "https://musicbrainz.org/ws/2/release"
_CAA_URL = "https://coverartarchive.org/release/{mbid}/front-250"
_USER_AGENT = "FuserCustomTool/1.0 (sgibb.code@gmail.com)"

_last_call = 0.0


def _throttle():
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _last_call = time.time()


def musicbrainz_lookup(artist: str, title: str) -> str | None:
    """Return a Cover Art Archive image URL for the given artist+title, or None."""
    try:
        _throttle()
        resp = requests.get(
            _MB_URL,
            params={"query": f'artist:"{artist}" recording:"{title}"', "fmt": "json", "limit": 5},
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        releases = resp.json().get("releases", [])
        if not releases:
            return None
        mbid = releases[0]["id"]

        _throttle()
        caa_resp = requests.get(
            _CAA_URL.format(mbid=mbid),
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
            allow_redirects=True,
        )
        if caa_resp.status_code == 200:
            return caa_resp.url
        return None
    except Exception:
        return None


def bulk_resolve(conn: sqlite3.Connection, progress_cb=None) -> None:
    """Look up art URLs for all songs where art_url IS NULL and source is not fusersoundlab."""
    rows = conn.execute(
        "SELECT id, source, artist, title FROM songs WHERE art_url IS NULL"
    ).fetchall()
    pending = [r for r in rows if r["source"] != "fusersoundlab"]
    total = len(pending)
    for i, row in enumerate(pending):
        if progress_cb:
            progress_cb(f"Resolving art… ({i + 1}/{total})")
        url = musicbrainz_lookup(row["artist"], row["title"])
        if not url:
            url = gdrive_art_lookup(row["artist"], status_cb=progress_cb)
        if url:
            update_art_url(conn, row["id"], url)
