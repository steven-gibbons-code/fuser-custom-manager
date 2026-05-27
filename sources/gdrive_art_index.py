"""GDrive art index: scrape the Fucuco album art repository and build a local index.

The public GDrive folder (14r8__8RAlxPc278yAe82ukq-aiRpgpC0) is organised as:

    Root/
        A/           <- letter folder
            Adele/   <- artist folder
                Adele - 21.jpg
                ...
        B/
            ...

Each folder page embeds a JS variable ``window['_DRIVE_ivd']`` whose value is a
single-quoted string of hex-escaped JSON.  The JSON has the shape:

    [[entry, entry, ...], null, null, null, [], 1]

Each ``entry`` is an array where:
    entry[0]  – file/folder ID (str)
    entry[1]  – list containing the parent folder ID, e.g. ["parent-id"]
    entry[2]  – name (str)
    entry[3]  – MIME type (str)

``build_index`` performs a 2-level crawl:
  1. Fetches the root folder page → finds letter folder entries (A, B, C...)
  2. For each letter folder, fetches that page → finds artist folder entries
  Returns ``{artist_name_lower: {folder_id: ..., files: []}}``.

``lookup`` fetches the artist folder on demand (one extra request per artist,
cached after the first call) and returns a direct download URL for the first image.
"""

import json
import re
import time
from pathlib import Path

import requests

FOLDER_ID = "14r8__8RAlxPc278yAe82ukq-aiRpgpC0"
_INDEX_PATH = Path.home() / ".fuser_manager" / "gdrive_art_index.json"
_TTL = 86400  # 24 hours

_FOLDER_MIME = "application/vnd.google-apps.folder"
_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

def _decode_drive_ivd(html: str) -> str | None:
    """Extract and decode the ``_DRIVE_ivd`` JS string from a GDrive folder page.

    The value is a single-quoted JS string that uses ``\\xHH`` hex escapes for
    double-quote characters and forward-slashes.  We walk the raw HTML bytes and
    decode those escape sequences manually.
    """
    m = re.search(r"_DRIVE_ivd'\]\s*=\s*'", html)
    if not m:
        return None
    pos = m.end()
    result: list[str] = []
    while pos < len(html):
        c = html[pos]
        if c == "'":
            break
        if c == "\\" and pos + 1 < len(html):
            nc = html[pos + 1]
            if nc == "x" and pos + 3 < len(html):
                hx = html[pos + 2 : pos + 4]
                try:
                    result.append(chr(int(hx, 16)))
                    pos += 4
                    continue
                except ValueError:
                    pass
            elif nc == "\\":
                result.append("\\")
                pos += 2
                continue
            elif nc == "/":
                result.append("/")
                pos += 2
                continue
            elif nc == '"':
                result.append('"')
                pos += 2
                continue
            elif nc == "n":
                result.append("\n")
                pos += 2
                continue
            elif nc == "u" and pos + 5 < len(html):
                hx = html[pos + 2 : pos + 6]
                try:
                    result.append(chr(int(hx, 16)))
                    pos += 6
                    continue
                except ValueError:
                    pass
        result.append(c)
        pos += 1
    return "".join(result)


def _parse_html(html: str) -> list[dict]:
    """Return a flat list of ``{id, name, mime, parent_id}`` dicts from one GDrive page."""
    raw = _decode_drive_ivd(html)
    if raw is None:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list) or not data or not isinstance(data[0], list):
        return []
    entries = []
    for item in data[0]:
        if not isinstance(item, list) or len(item) < 4:
            continue
        entry_id = item[0]
        parents = item[1]
        name = item[2]
        mime = item[3]
        if not isinstance(entry_id, str) or not isinstance(name, str):
            continue
        parent_id = parents[0] if isinstance(parents, list) and parents else None
        entries.append({"id": entry_id, "name": name, "mime": mime or "", "parent_id": parent_id})
    return entries


def _filter_images(files: list[dict]) -> list[dict]:
    """Filter a list of file entries, returning only image files."""
    return [
        f for f in files
        if Path(f["name"]).suffix.lower() in _IMG_EXTS
        or f.get("mime", "").startswith("image/")
    ]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _fetch_folder(folder_id: str) -> str:
    """Fetch the HTML of a GDrive folder page."""
    resp = requests.get(
        f"https://drive.google.com/drive/folders/{folder_id}",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.text


# ---------------------------------------------------------------------------
# Index persistence
# ---------------------------------------------------------------------------

def _save_index(index: dict) -> None:
    """Persist the index to disk."""
    _INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    _INDEX_PATH.write_text(
        json.dumps({"ts": time.time(), "index": index}),
        encoding="utf-8",
    )


def _load_index(build_cb=None) -> dict:
    """Load the index from disk cache if fresh; otherwise rebuild from Drive."""
    if _INDEX_PATH.exists():
        try:
            data = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
            if time.time() - data.get("ts", 0) < _TTL:
                return data["index"]
        except (json.JSONDecodeError, KeyError):
            pass

    if build_cb:
        build_cb("Building GDrive art index…")
    index = build_index(FOLDER_ID)
    _save_index(index)
    return index


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_index(folder_id: str, html: str | None = None) -> dict:
    """Build ``{artist_lower: {folder_id, files: []}}`` by crawling root + letter folders.

    Pass ``html`` directly in tests to supply the root page; real builds pass
    ``None`` to trigger HTTP fetches.

    The crawl is 2 levels deep:
      1. Parse the root page → find letter folder entries (A, B, C...).
      2. For each letter folder, fetch that page → find artist folder entries.

    ``files`` is left empty; it is populated lazily by ``lookup`` on first use.
    """
    if html is None:
        html = _fetch_folder(folder_id)

    root_entries = _parse_html(html)
    letter_folder_ids = [e["id"] for e in root_entries if e.get("mime") == _FOLDER_MIME]

    index: dict[str, dict] = {}
    for lf_id in letter_folder_ids:
        try:
            lf_html = _fetch_folder(lf_id)
            artist_entries = _parse_html(lf_html)
            for entry in artist_entries:
                if entry.get("mime") == _FOLDER_MIME:
                    key = entry["name"].strip().lower()
                    index[key] = {"folder_id": entry["id"], "files": []}
        except Exception:
            continue
    return index


def get_index() -> dict:
    """Return the art index, rebuilding from Drive if the cache is stale."""
    return _load_index()


def lookup(artist: str, status_cb=None) -> str | None:
    """Return a direct download URL for the first image matching *artist*, or None.

    On first call for an artist, fetches the artist's GDrive folder to populate
    ``files``; the result is cached to disk so subsequent calls are free.
    """
    key = artist.strip().lower()
    index = _load_index(build_cb=status_cb)
    entry = index.get(key)
    if not entry:
        return None

    if not entry.get("files"):
        # Fetch artist folder on demand to get image list
        try:
            html = _fetch_folder(entry["folder_id"])
            all_entries = _parse_html(html)
            images = _filter_images(all_entries)
            entry["files"] = [{"id": e["id"], "name": e["name"]} for e in images]
            _save_index(index)
        except Exception:
            return None

    if not entry["files"]:
        return None
    file_id = entry["files"][0]["id"]
    return f"https://drive.google.com/uc?id={file_id}&export=download"
