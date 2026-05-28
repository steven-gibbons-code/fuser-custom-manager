import time
import sqlite3
import threading
import requests

from db import (
    get_songs_pending_art,
    get_or_create_album_art, link_song_album_art, ART_DIR as _DEFAULT_ART_DIR,
)
from sources.gdrive_art_index import lookup as gdrive_art_lookup

_ITUNES_URL = "https://itunes.apple.com/search"
_USER_AGENT = "FuserCustomTool/1.0 (sgibb.code@gmail.com)"

_ITUNES_LOCK = threading.Lock()
_ITUNES_LAST_CALL = 0.0


def _itunes_throttle() -> None:
    """Enforce ~3 req/sec globally across all threads for iTunes API calls."""
    global _ITUNES_LAST_CALL
    with _ITUNES_LOCK:
        now = time.time()
        wait = 0.35 - (now - _ITUNES_LAST_CALL)
        if wait > 0:
            time.sleep(wait)
        _ITUNES_LAST_CALL = time.time()


def itunes_lookup(artist: str, title: str) -> tuple[str, str] | None:
    """Return (album_name, artwork_url) for the given artist+title, or None."""
    try:
        _itunes_throttle()
        resp = requests.get(
            _ITUNES_URL,
            params={"term": f"{artist} {title}", "entity": "song", "limit": 5},
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        results = resp.json().get("results", [])
        if not results:
            return None
        track = results[0]
        album = track.get("collectionName", "")
        artwork = track.get("artworkUrl100", "")
        if not album or not artwork:
            return None
        artwork = artwork.replace("100x100bb", "600x600bb")
        return album, artwork
    except Exception:
        return None


def bulk_resolve(conn: sqlite3.Connection, progress_cb=None, art_dir=None) -> None:
    """Look up art for all pending songs (album_art_id IS NULL, non-fusersoundlab)."""
    if art_dir is None:
        art_dir = _DEFAULT_ART_DIR
    art_dir.mkdir(parents=True, exist_ok=True)

    pending = get_songs_pending_art(conn)
    total = len(pending)
    for i, row in enumerate(pending):
        if progress_cb:
            progress_cb(f"Resolving art… ({i + 1}/{total})")

        itunes_result = itunes_lookup(row["artist"], row["title"])
        if itunes_result:
            album_name, art_url = itunes_result
        else:
            gdrive_url = gdrive_art_lookup(row["artist"], status_cb=progress_cb)
            if gdrive_url:
                album_name, art_url = "__artist__", gdrive_url
            else:
                continue

        album_art_id = get_or_create_album_art(conn, row["artist"], album_name, art_url)
        dest = art_dir / f"{album_art_id}.jpg"
        if not dest.exists():
            try:
                resp = requests.get(art_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    dest.write_bytes(resp.content)
            except Exception:
                pass
        link_song_album_art(conn, row["id"], album_art_id)
