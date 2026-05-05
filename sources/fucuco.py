import csv
import io
import re
from datetime import date

import requests

SHEET_ID = "1LdMeksBBV8YHo1rfgEWAfegEyRIhcGUjv96RNd10YKk"
TABS = [
    ("FULL DATABASE",   "fucuco_main"),
    ("VGM",             "fucuco_vgm"),
    ("NEW SUBMISSIONS", "fucuco_new"),
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


def normalise_row(row: dict, source: str) -> dict | None:
    h = list(row.keys())
    link = row.get(_find(h, "Link") or "", "").strip()
    if not link:
        return None

    new_sub_col = _find(h, "NEW SUBMISSIONS")
    # "FULL DATABASE Artist" is used in the main tab; "Artist" in others
    artist_col  = _find(h, "Artist", "Video Game Music Artist", "FULL DATABASE Artist")
    title_col   = _find(h, "Title")

    if source == "fucuco_new" and new_sub_col:
        combined = row.get(new_sub_col, "")
        if " - " in combined:
            artist, title = [p.strip() for p in combined.split(" - ", 1)]
        else:
            artist, title = "", combined.strip()
    else:
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
    bpm_col      = _find(h, "BPM")
    key_col      = _find(h, "Form Key", "Key")
    origin_col   = _find(h, "Origin")

    return {
        "source":         source,
        "artist":         artist,
        "title":          title,
        "creator":        row.get(creator_col or "", "").strip(),
        "genre":          row.get(genre_col   or "", "").strip(),
        "year":           _year(row.get(year_col or "", "")),
        "bpm":            _int(row.get(bpm_col  or "", "")),
        "key":            row.get(key_col    or "", "").strip(),
        "de_status":      row.get(de_col     or "", "").strip(),
        "complete":       row.get(complete_col or "", "").strip(),
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

    # Deduplicate headers: blank or repeated names get a positional key (_col0, _col1, ...)
    # This preserves DE STATUS (_col0) and Complete (_col1) which have blank labels in
    # the FULL DATABASE and VGM tabs.
    seen: set[str] = set()
    headers: list[str] = []
    for i, h in enumerate(raw[0]):
        key = h.strip()
        if not key or key in seen:
            key = f"_col{i}"
        seen.add(key)
        headers.append(key)

    songs = []
    for row in raw[1:]:
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
