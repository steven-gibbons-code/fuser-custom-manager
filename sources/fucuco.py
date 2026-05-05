import csv
import io
import re
from datetime import date

import requests

SHEET_ID = "1LdMeksBBV8YHo1rfgEWAfegEyRIhcGUjv96RNd10YKk"
TABS = [
    ("FULL DATABASE",   "fucuco_main"),
    ("VGM",             "fucuco_vgm"),
]


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
        songs.extend(fetch_tab(tab_name, source))
    return songs