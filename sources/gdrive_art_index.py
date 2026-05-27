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

``build_index`` takes the HTML of a single folder page and returns a mapping
``{artist_name_lower: {files: [{id, name}]}}``.  It works by:
  1. Parsing all entries out of ``_DRIVE_ivd``.
  2. Treating entries whose MIME is ``application/vnd.google-apps.folder`` as
     artist folders.
  3. Treating entries whose MIME starts with ``image/`` (or whose extension is a
     known image extension) as image files.
  4. Matching image files to artist folders via the parent-ID field (entry[1][0]).

This design allows both a real multi-request build (fetch letter folder → get
artist folders + their image children) and a single-HTML test path where the
mock HTML contains both folder and file entries together.
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


def _is_image(entry: dict) -> bool:
    mime = entry.get("mime", "")
    if mime.startswith("image/"):
        return True
    ext = Path(entry.get("name", "")).suffix.lower()
    return ext in _IMG_EXTS


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_index(folder_id: str, html: str | None = None) -> dict:
    """Return ``{artist_name_lower: {files: [{id, name}]}}`` for a GDrive folder.

    Pass ``html`` directly in tests; ``None`` triggers a real HTTP fetch of
    ``folder_id``.

    The function parses a single folder page.  It expects the page to contain
    both artist-folder entries and their child image-file entries in the same
    ``_DRIVE_ivd`` blob (as produced by the real GDrive UI when the folder
    view embeds all visible items), or as constructed in test fixtures.

    Artist folders are identified by ``mime == application/vnd.google-apps.folder``.
    Image files are matched to their parent artist folder via ``entry[1][0]``
    (the parent ID field).
    """
    if html is None:
        resp = requests.get(
            f"https://drive.google.com/drive/folders/{folder_id}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        resp.raise_for_status()
        html = resp.text

    entries = _parse_html(html)

    # Build lookup: folder_id → artist name
    artist_by_id: dict[str, str] = {}
    for e in entries:
        if e["mime"] == _FOLDER_MIME:
            artist_by_id[e["id"]] = e["name"].strip()

    # Collect images grouped by parent folder ID
    images_by_parent: dict[str, list[dict]] = {}
    for e in entries:
        if _is_image(e) and e["parent_id"]:
            images_by_parent.setdefault(e["parent_id"], []).append(
                {"id": e["id"], "name": e["name"]}
            )

    index: dict[str, dict] = {}
    for fid, artist_name in artist_by_id.items():
        images = images_by_parent.get(fid, [])
        if images:
            index[artist_name.lower()] = {"files": images}

    return index


def _load_index() -> dict:
    """Load the index from disk cache if fresh; otherwise rebuild from Drive."""
    if _INDEX_PATH.exists():
        try:
            data = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
            if time.time() - data.get("ts", 0) < _TTL:
                return data["index"]
        except (json.JSONDecodeError, KeyError):
            pass

    index = build_index(FOLDER_ID)
    _INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    _INDEX_PATH.write_text(
        json.dumps({"ts": time.time(), "index": index}),
        encoding="utf-8",
    )
    return index


def get_index() -> dict:
    """Return the art index, rebuilding from Drive if the cache is stale."""
    return _load_index()


def lookup(artist: str) -> str | None:
    """Return a direct download URL for the first image matching *artist*, or None."""
    key = artist.strip().lower()
    index = _load_index()
    entry = index.get(key)
    if not entry or not entry.get("files"):
        return None
    file_id = entry["files"][0]["id"]
    return f"https://drive.google.com/uc?id={file_id}&export=download"
