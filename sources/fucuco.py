import csv
import io
import re
from datetime import date

import requests

SHEET_ID = "1LdMeksBBV8YHo1rfgEWAfegEyRIhcGUjv96RNd10YKk"
SHEET_URL = "https://docs.google.com/spreadsheets/d/" + SHEET_ID

TABS = [
    ("FULL DATABASE",   "fucuco_main"),
    ("VGM",             "fucuco_vgm"),
    ("PACKS",           "fucuco_packs"),
]

# Map source to a human label and the sheet tab gid/name for linking
SOURCE_SHEET_TABS = {
    "fucuco_main":   "FULL DATABASE",
    "fucuco_vgm":    "VGM",
    "fucuco_packs":  "PACKS",
    "fucuco_new":    "NEW SUBMISSIONS",
}


def get_sheet_tab_url(source: str) -> str | None:
    """Return a URL to the specific sheet tab for a given source.

    Returns None if the source has no associated sheet tab.
    """
    tab = SOURCE_SHEET_TABS.get(source)
    if tab:
        return f"{SHEET_URL}/gid=0#gid=0&sheet={tab.replace(' ', '+')}"
    return None


def detect_link_host(url: str) -> str:
    if not url:
        return "other"
    u = url.lower()
    if "drive.google.com" in u:
        return "gdrive"
    if "1drv.ms" in u or "onedrive.live.com" in u:
        return "onedrive"
    if "mediafire.com" in u:
        return "mediafire"
    if "mega.nz" in u or "mega.co.nz" in u:
        return "mega"
    return "other"


def _find(headers: list[str], *candidates: str) -> str | None:
    lower = [h.lower().strip() for h in headers]
    for c in candidates:
        if c.lower() in lower:
            return headers[lower.index(c.lower())]
    return None


def _int(val: str) -> int | None:
    try:
        return int(val.strip())
    except (ValueError, AttributeError):
        return None


def _year(val: str) -> int | None:
    m = re.search(r"\d{4}", val or "")
    return int(m.group()) if m else None


def _is_ref_error(val: str) -> bool:
    """Detect Google Sheets formula errors like #REF!, #N/A, #VALUE! etc."""
    return bool(val and val.startswith("#"))


def normalise_row(row: dict, source: str) -> dict | None:
    h = list(row.keys())
    link = row.get(_find(h, "Link") or "", "").strip()
    if not link or _is_ref_error(link):
        return None

    # "FULL DATABASE Artist" is used in the main tab; "Artist" in others
    artist_col  = _find(h, "Artist", "Video Game Music Artist", "FULL DATABASE Artist")
    title_col   = _find(h, "Title")
    artist = row.get(artist_col or "", "").strip()
    title  = row.get(title_col or "", "").strip()

    if not artist and not title:
        return None

    # Blank-header columns (DE STATUS=_col0, Complete=_col1) are deduped
    # positionally by fetch_tab when the sheet has no explicit column label
    de_col       = _find(h, "DE STATUS", "_col0")
    complete_col = _find(h, "Complete",  "_col1")
    notes_col    = _find(h, "Update Fix Notes", "Form Notes", "Notes")
    stream_col   = _find(h, "Stream-optimized")
    creator_col  = _find(h, "Creator", "Author")
    genre_col    = _find(h, "Genre", "Genre/Year")
    year_col     = _find(h, "Year")
    bpm_col      = _find(h, "BPM", "BPM ")
    key_col      = _find(h, "Form Key", "Key")
    origin_col   = _find(h, "Origin")

    de_val = row.get(de_col or "", "").strip()
    if _is_ref_error(de_val):
        de_val = ""

    complete_val = row.get(complete_col or "", "").strip()
    if _is_ref_error(complete_val):
        complete_val = ""

    return {
        "source":         source,
        "artist":         artist,
        "title":          title,
        "creator":        row.get(creator_col or "", "").strip(),
        "genre":          row.get(genre_col   or "", "").strip(),
        "year":           _year(row.get(year_col or "", "")),
        "bpm":            _int(row.get(bpm_col  or "", "")),
        "key":            row.get(key_col    or "", "").strip(),
        "de_status":      de_val,
        "complete":       complete_val,
        "complete_notes": row.get(notes_col  or "", "").strip(),
        "stream_opt":     1 if row.get(stream_col or "", "").strip() == "1" else 0,
        "origin":         row.get(origin_col or "", "").strip() or None,
        "link":           link,
        "link_host":      detect_link_host(link),
        "last_seen":      date.today().isoformat(),
    }


# ── PACKS tab (pack-based format via export API) ────────────────────

# The PACKS tab has a completely different layout from the main tabs & VGM.
# It is a pack-submission tracker with these columns:
#   Creator | Title (pack name) | N° | V | Download (host) | Date | Content
#
# The Content column contains newline-separated entries like "Artist - Title".
# We parse each Content line as a separate song.
# Because the gviz API returns broken data for this tab when accessed by name,
# we use the export API instead.

_PACK_HEADER_KEYWORDS = {"creator", "title", "download", "content", "date"}


def _is_pack_header_row(row: list[str]) -> bool:
    """Detect if a row looks like a PACKS tab header row."""
    lower = [c.lower().strip() for c in row if c]
    matches = sum(1 for l in lower if l in _PACK_HEADER_KEYWORDS)
    return matches >= 3


_SONG_ARTIST_TITLE_RE = re.compile(r"^(?P<artist>.+?)\s*[-–—]\s*(?P<title>.+)$")


def _split_pack_songs(content: str) -> list[tuple[str, str]]:
    """Parse newline-separated content into (artist, title) pairs.

    Supports:
      "Artist - Title"          standard dash separator
      "Artist – Title"          en-dash separator
      "Artist — Title"          em-dash separator
      "Title" (no dash)         fallback: artist empty, title is the line
    """
    songs = []
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = _SONG_ARTIST_TITLE_RE.match(line)
        if m:
            songs.append((m.group("artist").strip(), m.group("title").strip()))
        else:
            songs.append(("", line))
    return songs


def _fetch_pack_tab() -> list[dict]:
    """Fetch and parse the PACKS tab.

    Uses the export API (which returns all rows) instead of gviz (which
    returns broken data for this tab when accessed by name).
    """
    url = (f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
           f"/export?format=csv&sheet=PACKS")
    resp = requests.get(url, timeout=30, allow_redirects=True)
    resp.raise_for_status()

    raw = list(csv.reader(io.StringIO(resp.text)))
    if not raw:
        return []

    # Find the header row (looks for: Creator, Title, Download, Content, etc.)
    header_idx = None
    for i, row in enumerate(raw):
        if _is_pack_header_row(row):
            header_idx = i
            break
    if header_idx is None:
        return []

    headers = [h.strip() for h in raw[header_idx]]
    songs = []

    for row in raw[header_idx + 1:]:
        # Skip blank rows
        if not any(c.strip() for c in row):
            continue
        row_dict = dict(zip(headers, row))

        creator = row_dict.get("Creator", "").strip()
        pack_name = row_dict.get("Title", "").strip()
        link = row_dict.get("Download", "").strip()
        content = row_dict.get("Content", "").strip()

        if not content:
            continue

        # Parse each line in Content as Artist - Title
        for artist, title in _split_pack_songs(content):
            if not title:
                continue
            song = {
                "source":         "fucuco_packs",
                "artist":         artist or creator,
                "title":          title,
                "creator":        creator,
                "genre":          "",
                "year":           None,
                "bpm":            None,
                "key":            "",
                "de_status":      "",
                "complete":       "",
                "complete_notes": pack_name,
                "stream_opt":     0,
                "origin":         None,
                "link":           link,
                "link_host":      detect_link_host(link),
                "last_seen":      date.today().isoformat(),
            }
            songs.append(song)

    return songs


# ── Standard tab fetcher (FULL DATABASE / VGM) ──────────────────────


def fetch_tab(tab_name: str, source: str) -> list[dict]:
    url = (f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
           f"/gviz/tq?tqx=out:csv&sheet={tab_name.replace(' ', '+')}")
    resp = requests.get(url, timeout=30, allow_redirects=True)
    resp.raise_for_status()

    raw = list(csv.reader(io.StringIO(resp.text)))
    if not raw:
        return []

    # Some tabs have a filter/search row as the first row.
    # Detect this and skip it to find the real header row.
    header_start = 0
    if raw and raw[0] and any("SEARCH" in (c or "").upper() for c in raw[0]):
        # The first row is a search/filter row — look for the next row with
        # actual column-like headers (text that looks like column names)
        for i in range(1, len(raw)):
            non_empty = [c for c in raw[i] if c and c.strip()]
            if len(non_empty) >= 3:
                header_start = i
                break

    # Deduplicate headers: blank or repeated names get a positional key (_col0, _col1, ...)
    # This preserves DE STATUS (_col0) and Complete (_col1) which have blank labels in
    # the FULL DATABASE and VGM tabs.
    seen: set[str] = set()
    headers: list[str] = []
    for i, h in enumerate(raw[header_start]):
        key = h.strip()
        if not key or key in seen:
            key = f"_col{i}"
        seen.add(key)
        headers.append(key)

    songs = []
    for row in raw[header_start + 1:]:
        # Skip blank rows
        if not any(c.strip() for c in row):
            continue
        row_dict = dict(zip(headers, row))
        result = normalise_row(row_dict, source)
        if result:
            songs.append(result)
    return songs


def fetch_all() -> list[dict]:
    songs = []
    for tab_name, source in TABS:
        if source == "fucuco_packs":
            songs.extend(_fetch_pack_tab())
        else:
            songs.extend(fetch_tab(tab_name, source))
    return songs