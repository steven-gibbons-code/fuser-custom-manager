# Fuser Custom Song Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Python GUI app that fetches custom Fuser song listings from fucuco.online (Google Sheets CSV) and fusersoundlab.com (HTML scrape), caches them in SQLite, and lets the user browse, download, and install `.pak`+`.sig` song file pairs into `C:\Fuser\Fuser\Content\Paks\custom_songs\<artist>\`.

**Architecture:** Source modules normalise rows from Google Sheets CSV and HTML scraping into a shared schema stored in SQLite. A downloader routes links by host (gdown for Google Drive, manual prompt for others), validates `.pak`/`.sig` output, and passes results to an installer that places files under the custom songs directory. A `customtkinter` GUI reads from SQLite and dispatches downloads on background threads with live progress.

**Tech Stack:** Python 3.11+, customtkinter 5.2+, requests, beautifulsoup4, gdown, sqlite3 (built-in), pytest.

---

## File Map

```
C:\Users\sgibb\Documents\ClaudeCode\fuser-custom-tool\
    app.py                    # Entry point — python app.py to launch
    db.py                     # SQLite init, upsert, query, install tracking
    downloader.py             # Link routing, gdown, pak/sig validation
    installer.py              # File placement, scan, uninstall
    sources/
        __init__.py
        fucuco.py             # Fetch 3 Google Sheet tabs, normalise rows
        fusersoundlab.py      # Scrape fusersoundlab.com HTML, normalise rows
    gui/
        __init__.py
        main_window.py        # Top-level CTk window, wires all components
        song_table.py         # Paginated sortable filterable ttk.Treeview
        detail_panel.py       # Right panel: metadata, Download, Uninstall
        status_bar.py         # Download progress, queue, error messages
    tests/
        __init__.py
        test_db.py
        test_fucuco.py
        test_fusersoundlab.py
        test_downloader.py
        test_installer.py
        test_gui_smoke.py
    requirements.txt
```

---

### Task 1: Project scaffold

**Files:**
- Create: `requirements.txt`
- Create: `sources\__init__.py`
- Create: `gui\__init__.py`
- Create: `tests\__init__.py`

- [ ] **Step 1: Create directory structure**

Run in PowerShell from `C:\Users\sgibb\Documents\ClaudeCode\fuser-custom-tool`:
```powershell
New-Item -ItemType Directory -Force sources, gui, tests | Out-Null
New-Item -ItemType File -Force sources\__init__.py, gui\__init__.py, tests\__init__.py | Out-Null
```

- [ ] **Step 2: Create requirements.txt**

```
customtkinter==5.2.2
requests==2.31.0
beautifulsoup4==4.12.3
gdown==5.1.0
pytest==8.1.1
```

- [ ] **Step 3: Install dependencies**

```powershell
pip install -r requirements.txt
```

Expected: All five packages install without error.

- [ ] **Step 4: Initialise git and commit**

```powershell
git init
git add requirements.txt sources\__init__.py gui\__init__.py tests\__init__.py
git commit -m "chore: project scaffold"
```

---

### Task 2: Database layer

**Files:**
- Create: `db.py`
- Create: `tests\test_db.py`

- [ ] **Step 1: Write failing tests**

Create `tests\test_db.py`:

```python
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))
from db import init_db, upsert_songs, get_songs, mark_installed, mark_uninstalled, get_installed

SONG = {
    "source": "fucuco_main", "artist": "Daft Punk", "title": "Get Lucky",
    "creator": "DJTest", "genre": "Pop", "year": 2013, "bpm": 116,
    "key": "A Minor", "de_status": "Eligible", "complete": "C",
    "complete_notes": "", "stream_opt": 1, "origin": None,
    "link": "https://drive.google.com/file/d/abc", "link_host": "gdrive",
    "last_seen": "2026-05-05",
}

@pytest.fixture
def conn(tmp_path):
    c = init_db(tmp_path / "test.db")
    yield c
    c.close()

def test_init_creates_tables(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "songs" in tables
    assert "installed" in tables

def test_upsert_inserts_new_song(conn):
    upsert_songs(conn, [SONG])
    rows = get_songs(conn, {})
    assert len(rows) == 1
    assert rows[0]["artist"] == "Daft Punk"

def test_upsert_updates_existing(conn):
    upsert_songs(conn, [SONG])
    updated = {**SONG, "bpm": 120}
    upsert_songs(conn, [updated])
    rows = get_songs(conn, {})
    assert len(rows) == 1
    assert rows[0]["bpm"] == 120

def test_mark_and_unmark_installed(conn):
    upsert_songs(conn, [SONG])
    song = get_songs(conn, {})[0]
    mark_installed(conn, song["id"],
                   r"C:\Fuser\Fuser\Content\Paks\custom_songs\Daft Punk\Get Lucky.pak",
                   r"C:\Fuser\Fuser\Content\Paks\custom_songs\Daft Punk\Get Lucky.sig")
    installed = get_installed(conn)
    assert len(installed) == 1
    assert installed[0]["pak_path"].endswith("Get Lucky.pak")
    mark_uninstalled(conn, song["id"])
    assert get_installed(conn) == []

@pytest.mark.parametrize("complete,de_status,notes,expected", [
    ("D", "",          "",           True),
    ("C", "Eligible",  "",           True),
    ("C", "",          "",           True),
    ("C", "",          "Some issue", False),
    ("C", "Not eligible", "",        False),
    ("",  "Eligible",  "",           False),
])
def test_is_definitive(conn, complete, de_status, notes, expected):
    song = {**SONG, "complete": complete, "de_status": de_status, "complete_notes": notes}
    upsert_songs(conn, [song])
    rows = get_songs(conn, {})
    assert bool(rows[0]["is_definitive"]) == expected

def test_get_songs_search_filter(conn):
    upsert_songs(conn, [SONG])
    assert len(get_songs(conn, {"search": "Daft"})) == 1
    assert len(get_songs(conn, {"search": "Nonexistent"})) == 0

def test_get_songs_definitive_only_filter(conn):
    upsert_songs(conn, [SONG])  # Eligible + C = definitive
    assert len(get_songs(conn, {"definitive_only": True})) == 1
    not_def = {**SONG, "title": "Other", "complete": "", "de_status": ""}
    upsert_songs(conn, [not_def])
    assert len(get_songs(conn, {"definitive_only": True})) == 1
```

- [ ] **Step 2: Run to verify they fail**

```powershell
pytest tests\test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 3: Implement db.py**

Create `db.py`:

```python
import sqlite3
from datetime import datetime
from pathlib import Path

DB_DIR = Path.home() / ".fuser_manager"
DB_PATH = DB_DIR / "catalog.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id             INTEGER PRIMARY KEY,
    source         TEXT NOT NULL,
    artist         TEXT,
    title          TEXT,
    creator        TEXT,
    genre          TEXT,
    year           INTEGER,
    bpm            INTEGER,
    key            TEXT,
    de_status      TEXT,
    complete       TEXT,
    complete_notes TEXT,
    stream_opt     INTEGER DEFAULT 0,
    origin         TEXT,
    link           TEXT,
    link_host      TEXT,
    last_seen      TEXT,
    UNIQUE(source, artist, title)
);

CREATE TABLE IF NOT EXISTS installed (
    id           INTEGER PRIMARY KEY,
    song_id      INTEGER REFERENCES songs(id) ON DELETE CASCADE,
    pak_path     TEXT NOT NULL,
    sig_path     TEXT,
    installed_at TEXT NOT NULL
);
"""

_IS_DEFINITIVE = """
CASE
    WHEN s.complete = 'D' THEN 1
    WHEN s.de_status = 'Eligible' AND s.complete = 'C' THEN 1
    WHEN (s.de_status IS NULL OR s.de_status = '')
         AND s.complete = 'C'
         AND (s.complete_notes IS NULL OR s.complete_notes = '') THEN 1
    ELSE 0
END
"""


def init_db(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def upsert_songs(conn: sqlite3.Connection, songs: list[dict]) -> None:
    conn.executemany("""
        INSERT INTO songs (source, artist, title, creator, genre, year, bpm, key,
                           de_status, complete, complete_notes, stream_opt, origin,
                           link, link_host, last_seen)
        VALUES (:source, :artist, :title, :creator, :genre, :year, :bpm, :key,
                :de_status, :complete, :complete_notes, :stream_opt, :origin,
                :link, :link_host, :last_seen)
        ON CONFLICT(source, artist, title) DO UPDATE SET
            creator=excluded.creator, genre=excluded.genre, year=excluded.year,
            bpm=excluded.bpm, key=excluded.key, de_status=excluded.de_status,
            complete=excluded.complete, complete_notes=excluded.complete_notes,
            stream_opt=excluded.stream_opt, origin=excluded.origin,
            link=excluded.link, link_host=excluded.link_host,
            last_seen=excluded.last_seen
    """, songs)
    conn.commit()


def get_songs(conn: sqlite3.Connection, filters: dict) -> list[dict]:
    where, params = ["1=1"], []

    if filters.get("search"):
        where.append("(s.artist LIKE ? OR s.title LIKE ? OR s.creator LIKE ?)")
        t = f"%{filters['search']}%"
        params += [t, t, t]
    if filters.get("source"):
        where.append("s.source = ?")
        params.append(filters["source"])
    if filters.get("genre"):
        where.append("s.genre LIKE ?")
        params.append(f"%{filters['genre']}%")
    if filters.get("key"):
        where.append("s.key = ?")
        params.append(filters["key"])
    if filters.get("de_status"):
        where.append("s.de_status = ?")
        params.append(filters["de_status"])
    if filters.get("definitive_only"):
        where.append(f"({_IS_DEFINITIVE}) = 1")
    if filters.get("bpm_min") is not None:
        where.append("s.bpm >= ?")
        params.append(filters["bpm_min"])
    if filters.get("bpm_max") is not None:
        where.append("s.bpm <= ?")
        params.append(filters["bpm_max"])

    order = filters.get("order_by", "s.artist")
    direction = "DESC" if filters.get("descending") else "ASC"
    offset = filters.get("offset", 0)

    sql = f"""
        SELECT s.*, {_IS_DEFINITIVE} AS is_definitive,
               i.pak_path, i.sig_path, i.installed_at
        FROM songs s
        LEFT JOIN installed i ON i.song_id = s.id
        WHERE {' AND '.join(where)}
        ORDER BY {order} {direction}
        LIMIT 100 OFFSET ?
    """
    params.append(offset)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def mark_installed(conn: sqlite3.Connection, song_id: int,
                   pak_path: str, sig_path: str) -> None:
    conn.execute("DELETE FROM installed WHERE song_id = ?", (song_id,))
    conn.execute(
        "INSERT INTO installed (song_id, pak_path, sig_path, installed_at) VALUES (?,?,?,?)",
        (song_id, pak_path, sig_path, datetime.now().isoformat()),
    )
    conn.commit()


def mark_uninstalled(conn: sqlite3.Connection, song_id: int) -> None:
    conn.execute("DELETE FROM installed WHERE song_id = ?", (song_id,))
    conn.commit()


def get_installed(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT i.*, s.artist, s.title FROM installed i JOIN songs s ON s.id = i.song_id"
    ).fetchall()]
```

- [ ] **Step 4: Run to verify they pass**

```powershell
pytest tests\test_db.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add db.py tests\test_db.py
git commit -m "feat: database layer — schema, upsert, query, install tracking, is_definitive"
```

---

### Task 3: fucuco source fetcher

**Files:**
- Create: `sources\fucuco.py`
- Create: `tests\test_fucuco.py`

- [ ] **Step 1: Write failing tests**

Create `tests\test_fucuco.py`:

```python
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))
from sources.fucuco import normalise_row, detect_link_host

def test_normalise_full_db_row():
    row = {
        "DE STATUS": "Eligible", "Complete": "C", "Stream-optimized": "1",
        "Artist": "Daft Punk", "Title": "Get Lucky", "Creator": "DJTest",
        "Genre": "Pop", "Year": "2013", "BPM": "116", "Form Key": "A Minor",
        "Link": "https://drive.google.com/file/d/abc123",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["artist"] == "Daft Punk"
    assert r["title"] == "Get Lucky"
    assert r["bpm"] == 116
    assert r["key"] == "A Minor"
    assert r["complete"] == "C"
    assert r["de_status"] == "Eligible"
    assert r["link_host"] == "gdrive"
    assert r["stream_opt"] == 1
    assert r["source"] == "fucuco_main"

def test_normalise_vgm_row():
    row = {
        "Stream-optimized": "1", "Video Game Music Artist": "Nobuo Uematsu",
        "Title": "One-Winged Angel", "Creator": "FFfan",
        "Origin": "Final Fantasy VII", "Genre": "Classical",
        "Year": "1997", "BPM": "168", "Form Key": "E Minor",
        "Link": "https://drive.google.com/drive/folders/xyz",
    }
    r = normalise_row(row, "fucuco_vgm")
    assert r["artist"] == "Nobuo Uematsu"
    assert r["origin"] == "Final Fantasy VII"
    assert r["link_host"] == "gdrive"

def test_normalise_new_submissions_splits_artist_title():
    row = {
        "DE STATUS": "", "Complete": "C", "Stream-optimized": "0",
        "NEW SUBMISSIONS": "Taylor Swift - Anti-Hero",
        "BPM": "97", "Form Key": "F Major",
        "Link": "https://drive.google.com/file/d/def",
    }
    r = normalise_row(row, "fucuco_new")
    assert r["title"] == "Anti-Hero"
    assert r["artist"] == "Taylor Swift"

def test_normalise_skips_row_with_no_link():
    row = {"Artist": "No Link", "Title": "Song", "Link": ""}
    assert normalise_row(row, "fucuco_main") is None

@pytest.mark.parametrize("url,expected", [
    ("https://drive.google.com/file/d/abc", "gdrive"),
    ("https://drive.google.com/drive/folders/xyz", "gdrive"),
    ("https://1drv.ms/u/abc", "onedrive"),
    ("https://www.mediafire.com/file/abc", "mediafire"),
    ("https://mega.nz/file/abc", "mega"),
    ("https://example.com/file", "other"),
    ("", "other"),
])
def test_detect_link_host(url, expected):
    assert detect_link_host(url) == expected
```

- [ ] **Step 2: Run to verify they fail**

```powershell
pytest tests\test_fucuco.py -v
```

Expected: `ModuleNotFoundError: No module named 'sources.fucuco'`

- [ ] **Step 3: Implement sources/fucuco.py**

Create `sources\fucuco.py`:

```python
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
    artist_col  = _find(h, "Artist", "Video Game Music Artist")
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

    de_col       = _find(h, "DE STATUS")
    complete_col = _find(h, "Complete")
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
    reader = csv.DictReader(io.StringIO(resp.text))
    return [r for row in reader if (r := normalise_row(dict(row), source))]


def fetch_all() -> list[dict]:
    songs = []
    for tab_name, source in TABS:
        songs.extend(fetch_tab(tab_name, source))
    return songs
```

- [ ] **Step 4: Run to verify they pass**

```powershell
pytest tests\test_fucuco.py -v
```

Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add sources\fucuco.py tests\test_fucuco.py
git commit -m "feat: fucuco Google Sheets source — three tabs, normalised schema"
```

---

### Task 4: fusersoundlab scraper

**Files:**
- Create: `sources\fusersoundlab.py`
- Create: `tests\test_fusersoundlab.py`

- [ ] **Step 1: Write failing tests**

Create `tests\test_fusersoundlab.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from sources.fusersoundlab import parse_html

FIXTURE_HTML = """
<html><body>
<div class="track-item">
  <span class="track-title">Levitating</span>
  <span class="track-artist">Dua Lipa</span>
  <span class="track-bpm">103 BPM</span>
  <span class="track-key">G Major</span>
  <a class="download-link" href="https://drive.google.com/drive/folders/abc123">Download</a>
</div>
<div class="track-item">
  <span class="track-title">Blinding Lights</span>
  <span class="track-artist">The Weeknd</span>
  <span class="track-bpm">171 BPM</span>
  <span class="track-key">F Minor</span>
  <a class="download-link" href="https://drive.google.com/drive/folders/def456">Download</a>
</div>
</body></html>
"""

def test_parse_returns_two_songs():
    assert len(parse_html(FIXTURE_HTML)) == 2

def test_parse_fields():
    songs = parse_html(FIXTURE_HTML)
    s = songs[0]
    assert s["title"] == "Levitating"
    assert s["artist"] == "Dua Lipa"
    assert s["bpm"] == 103
    assert s["key"] == "G Major"
    assert s["link_host"] == "gdrive"
    assert s["source"] == "fusersoundlab"

def test_parse_skips_entry_without_link():
    html = '<div class="track-item"><span class="track-title">No Link</span></div>'
    assert parse_html(html) == []
```

- [ ] **Step 2: Run to verify they fail**

```powershell
pytest tests\test_fusersoundlab.py -v
```

Expected: `ModuleNotFoundError: No module named 'sources.fusersoundlab'`

- [ ] **Step 3: Implement sources/fusersoundlab.py**

Create `sources\fusersoundlab.py`:

```python
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
```

- [ ] **Step 4: Run to verify they pass**

```powershell
pytest tests\test_fusersoundlab.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add sources\fusersoundlab.py tests\test_fusersoundlab.py
git commit -m "feat: fusersoundlab HTML scraper"
```

---

### Task 5: Downloader

**Files:**
- Create: `downloader.py`
- Create: `tests\test_downloader.py`

- [ ] **Step 1: Write failing tests**

Create `tests\test_downloader.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from downloader import detect_host, find_pak_sig_pairs, DownloadResult

def test_detect_host_gdrive_file():
    assert detect_host("https://drive.google.com/file/d/abc123") == "gdrive"

def test_detect_host_gdrive_folder():
    assert detect_host("https://drive.google.com/drive/folders/xyz") == "gdrive"

def test_detect_host_onedrive():
    assert detect_host("https://1drv.ms/u/abc") == "onedrive"

def test_detect_host_other():
    assert detect_host("https://example.com/file") == "other"

def test_find_pairs_matched(tmp_path):
    (tmp_path / "song.pak").write_text("")
    (tmp_path / "song.sig").write_text("")
    (tmp_path / "readme.txt").write_text("")
    pairs = find_pak_sig_pairs(tmp_path)
    assert len(pairs) == 1
    assert pairs[0][0].name == "song.pak"
    assert pairs[0][1].name == "song.sig"

def test_find_pairs_missing_sig(tmp_path):
    (tmp_path / "song.pak").write_text("")
    pairs = find_pak_sig_pairs(tmp_path)
    assert len(pairs) == 1
    assert pairs[0][0].name == "song.pak"
    assert pairs[0][1] is None

def test_find_pairs_empty_dir(tmp_path):
    assert find_pak_sig_pairs(tmp_path) == []

def test_find_pairs_multiple(tmp_path):
    for name in ["a", "b"]:
        (tmp_path / f"{name}.pak").write_text("")
        (tmp_path / f"{name}.sig").write_text("")
    assert len(find_pak_sig_pairs(tmp_path)) == 2

def test_download_result_fields():
    r = DownloadResult(status="ok", pairs=[], error_msg=None, raw_url="https://x.com")
    assert r.status == "ok"
    assert r.raw_url == "https://x.com"
```

- [ ] **Step 2: Run to verify they fail**

```powershell
pytest tests\test_downloader.py -v
```

Expected: `ModuleNotFoundError: No module named 'downloader'`

- [ ] **Step 3: Implement downloader.py**

Create `downloader.py`:

```python
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import gdown
import requests

STAGING_DIR = Path.home() / ".fuser_manager" / "staging"


@dataclass
class DownloadResult:
    status:    str            # 'ok' | 'error' | 'manual'
    pairs:     list           # [(pak_path: Path, sig_path: Path | None), ...]
    error_msg: str | None
    raw_url:   str


def detect_host(url: str) -> str:
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


def find_pak_sig_pairs(directory: Path) -> list[tuple]:
    pairs = []
    for pak in sorted(directory.rglob("*.pak")):
        sig = pak.with_suffix(".sig")
        pairs.append((pak, sig if sig.exists() else None))
    return pairs


def download(url: str, progress_cb: Callable | None = None) -> DownloadResult:
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    work_dir = Path(tempfile.mkdtemp(dir=STAGING_DIR))
    host = detect_host(url)

    if host == "gdrive":
        return _gdrive(url, work_dir)

    # Non-gdrive: check liveness, then return manual prompt
    return _non_gdrive(url, work_dir)


def _gdrive(url: str, work_dir: Path) -> DownloadResult:
    try:
        is_folder = "drive/folders" in url.lower()
        if is_folder:
            gdown.download_folder(url, output=str(work_dir), quiet=False, use_cookies=False)
        else:
            gdown.download(url, str(work_dir / "download"), quiet=False, fuzzy=True)
    except Exception as exc:
        _rm(work_dir)
        return DownloadResult(status="error", pairs=[], error_msg=str(exc), raw_url=url)

    pairs = find_pak_sig_pairs(work_dir)
    if not pairs:
        _rm(work_dir)
        return DownloadResult(
            status="manual", pairs=[], error_msg="No .pak/.sig found in download", raw_url=url
        )
    return DownloadResult(status="ok", pairs=pairs, error_msg=None, raw_url=url)


def _non_gdrive(url: str, work_dir: Path) -> DownloadResult:
    _rm(work_dir)
    try:
        resp = requests.head(url, timeout=10, allow_redirects=True)
        if resp.status_code >= 400:
            return DownloadResult(
                status="error", pairs=[], error_msg=f"HTTP {resp.status_code}", raw_url=url
            )
    except requests.RequestException as exc:
        return DownloadResult(status="error", pairs=[], error_msg=str(exc), raw_url=url)
    return DownloadResult(status="manual", pairs=[], error_msg=None, raw_url=url)


def _rm(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)
```

- [ ] **Step 4: Run to verify they pass**

```powershell
pytest tests\test_downloader.py -v
```

Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add downloader.py tests\test_downloader.py
git commit -m "feat: downloader — gdrive via gdown, manual fallback, dead-link error"
```

---

### Task 6: Installer

**Files:**
- Create: `installer.py`
- Create: `tests\test_installer.py`

- [ ] **Step 1: Write failing tests**

Create `tests\test_installer.py`:

```python
import sys
import pytest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from installer import sanitise_artist, install_pairs, uninstall, scan_and_sync
from db import init_db, upsert_songs, get_songs, get_installed
from downloader import DownloadResult

BASE_SONG = {
    "source": "fucuco_main", "artist": "Daft Punk", "title": "Get Lucky",
    "creator": "", "genre": "", "year": 2013, "bpm": 116, "key": "A Minor",
    "de_status": "Eligible", "complete": "C", "complete_notes": "",
    "stream_opt": 1, "origin": None, "link": "x", "link_host": "gdrive",
    "last_seen": "2026-05-05",
}

@pytest.fixture
def conn(tmp_path):
    c = init_db(tmp_path / "test.db")
    yield c
    c.close()

def test_sanitise_strips_illegal_chars():
    assert sanitise_artist("AC/DC")         == "ACDC"
    assert sanitise_artist("Artist: Name")  == "Artist Name"
    assert sanitise_artist("  Spaced  ")    == "Spaced"
    assert sanitise_artist("Bad\\Slash")    == "BadSlash"

def test_install_moves_pak_and_sig(tmp_path, conn):
    upsert_songs(conn, [BASE_SONG])
    song = get_songs(conn, {})[0]
    staging = tmp_path / "staging"
    staging.mkdir()
    pak = staging / "song.pak"
    sig = staging / "song.sig"
    pak.write_text("")
    sig.write_text("")
    result = DownloadResult(status="ok", pairs=[(pak, sig)], error_msg=None, raw_url="x")
    install_root = tmp_path / "custom_songs"
    install_pairs(result, song["id"], song["artist"], install_root, conn)
    installed = get_installed(conn)
    assert len(installed) == 1
    assert Path(installed[0]["pak_path"]).exists()
    assert Path(installed[0]["sig_path"]).exists()

def test_uninstall_removes_files_and_empty_dir(tmp_path, conn):
    upsert_songs(conn, [BASE_SONG])
    song = get_songs(conn, {})[0]
    staging = tmp_path / "staging"
    staging.mkdir()
    pak = staging / "song.pak"
    sig = staging / "song.sig"
    pak.write_text("")
    sig.write_text("")
    result = DownloadResult(status="ok", pairs=[(pak, sig)], error_msg=None, raw_url="x")
    install_root = tmp_path / "custom_songs"
    install_pairs(result, song["id"], song["artist"], install_root, conn)
    uninstall(song["id"], install_root, conn)
    assert get_installed(conn) == []
    assert not (install_root / "Daft Punk").exists()

def test_scan_and_sync_picks_up_existing_files(tmp_path, conn):
    upsert_songs(conn, [BASE_SONG])
    install_root = tmp_path / "custom_songs"
    artist_dir = install_root / "Daft Punk"
    artist_dir.mkdir(parents=True)
    (artist_dir / "Get Lucky.pak").write_text("")
    (artist_dir / "Get Lucky.sig").write_text("")
    scan_and_sync(install_root, conn)
    assert len(get_installed(conn)) == 1
```

- [ ] **Step 2: Run to verify they fail**

```powershell
pytest tests\test_installer.py -v
```

Expected: `ModuleNotFoundError: No module named 'installer'`

- [ ] **Step 3: Implement installer.py**

Create `installer.py`:

```python
import re
import shutil
import sqlite3
from pathlib import Path

from db import mark_installed, mark_uninstalled, get_installed, get_songs
from downloader import DownloadResult

INSTALL_DIR = Path(r"C:\Fuser\Fuser\Content\Paks\custom_songs")
_ILLEGAL = re.compile(r'[<>:"/\\|?*]')


def sanitise_artist(name: str) -> str:
    return " ".join(_ILLEGAL.sub("", name).split())


def install_pairs(result: DownloadResult, song_id: int, artist: str,
                  install_root: Path, conn: sqlite3.Connection) -> None:
    artist_dir = install_root / sanitise_artist(artist)
    artist_dir.mkdir(parents=True, exist_ok=True)
    for pak_src, sig_src in result.pairs:
        pak_dst = artist_dir / pak_src.name
        shutil.move(str(pak_src), str(pak_dst))
        sig_dst = ""
        if sig_src and sig_src.exists():
            sig_dst_path = artist_dir / sig_src.name
            shutil.move(str(sig_src), str(sig_dst_path))
            sig_dst = str(sig_dst_path)
        mark_installed(conn, song_id, str(pak_dst), sig_dst)


def uninstall(song_id: int, install_root: Path, conn: sqlite3.Connection) -> None:
    for rec in get_installed(conn):
        if rec["song_id"] != song_id:
            continue
        for key in ("pak_path", "sig_path"):
            p = Path(rec[key]) if rec.get(key) else None
            if p and p.exists():
                p.unlink()
        artist_dir = Path(rec["pak_path"]).parent
        if artist_dir.exists() and not any(artist_dir.iterdir()):
            artist_dir.rmdir()
    mark_uninstalled(conn, song_id)


def scan_and_sync(install_root: Path, conn: sqlite3.Connection) -> None:
    if not install_root.exists():
        return
    index = {
        (s["artist"].lower(), s["title"].lower()): s["id"]
        for s in get_songs(conn, {})
    }
    for pak in install_root.rglob("*.pak"):
        sig = pak.with_suffix(".sig")
        key = (pak.parent.name.lower(), pak.stem.lower())
        if (song_id := index.get(key)):
            mark_installed(conn, song_id, str(pak), str(sig) if sig.exists() else "")
```

- [ ] **Step 4: Run to verify they pass**

```powershell
pytest tests\test_installer.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add installer.py tests\test_installer.py
git commit -m "feat: installer — place pak/sig, uninstall, startup scan"
```

---

### Task 7: GUI skeleton and main window

**Files:**
- Create: `gui\main_window.py`
- Create: `gui\song_table.py` (stub)
- Create: `gui\detail_panel.py` (stub)
- Create: `gui\status_bar.py` (stub)
- Create: `tests\test_gui_smoke.py`

- [ ] **Step 1: Write smoke test**

Create `tests\test_gui_smoke.py`:

```python
def test_gui_imports():
    from gui.main_window import FuserApp
    from gui.song_table import SongTable
    from gui.detail_panel import DetailPanel
    from gui.status_bar import StatusBar
    assert FuserApp and SongTable and DetailPanel and StatusBar
```

- [ ] **Step 2: Create stubs so the import test passes**

Create `gui\song_table.py`:
```python
class SongTable:
    pass
```

Create `gui\detail_panel.py`:
```python
class DetailPanel:
    pass
```

Create `gui\status_bar.py`:
```python
class StatusBar:
    pass
```

Create `gui\main_window.py`:
```python
class FuserApp:
    pass
```

- [ ] **Step 3: Run smoke test to verify it passes**

```powershell
pytest tests\test_gui_smoke.py -v
```

Expected: PASS.

- [ ] **Step 4: Replace gui/main_window.py with full implementation**

Replace `gui\main_window.py`:

```python
import sqlite3
import threading
from datetime import date

import customtkinter as ctk

from db import init_db, get_songs, upsert_songs
from downloader import download
from installer import scan_and_sync, install_pairs, uninstall, INSTALL_DIR
from sources.fucuco import fetch_all as fetch_fucuco
from sources.fusersoundlab import fetch_all as fetch_fsl
from gui.song_table import SongTable
from gui.detail_panel import DetailPanel
from gui.status_bar import StatusBar

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class FuserApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Fuser Custom Song Manager")
        self.geometry("1200x800")
        self.conn: sqlite3.Connection = init_db()
        scan_and_sync(INSTALL_DIR, self.conn)
        self._build_ui()
        self._refresh_table()

    # ── Layout ────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=7)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(2, weight=1)

        # Row 0 — search + actions
        top = ctk.CTkFrame(self, height=48)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 0))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="Search:").grid(row=0, column=0, padx=6)
        self._search = ctk.StringVar()
        self._search.trace_add("write", lambda *_: self._refresh_table())
        ctk.CTkEntry(top, textvariable=self._search, width=240).grid(
            row=0, column=1, padx=4, sticky="ew")

        self._def_only = ctk.BooleanVar()
        ctk.CTkCheckBox(top, text="Definitive only", variable=self._def_only,
                         command=self._refresh_table).grid(row=0, column=2, padx=6)

        self._refresh_btn = ctk.CTkButton(top, text="Refresh Sources", width=130,
                                           command=self._start_refresh)
        self._refresh_btn.grid(row=0, column=3, padx=6)

        self._updated_lbl = ctk.CTkLabel(top, text="", text_color="#aaaaaa")
        self._updated_lbl.grid(row=0, column=4, padx=6)

        # Row 1 — filter bar
        fbar = ctk.CTkFrame(self, height=40)
        fbar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 0))

        SOURCES = ["All Sources", "fucuco_main", "fucuco_vgm", "fucuco_new", "fusersoundlab"]
        ctk.CTkLabel(fbar, text="Source:").pack(side="left", padx=6)
        self._source = ctk.StringVar(value="All Sources")
        ctk.CTkOptionMenu(fbar, variable=self._source, values=SOURCES, width=130,
                           command=lambda _: self._refresh_table()).pack(side="left", padx=4)

        ctk.CTkLabel(fbar, text="Genre:").pack(side="left", padx=(10, 4))
        self._genre = ctk.StringVar()
        self._genre.trace_add("write", lambda *_: self._refresh_table())
        ctk.CTkEntry(fbar, textvariable=self._genre, width=100).pack(side="left", padx=2)

        ctk.CTkLabel(fbar, text="BPM:").pack(side="left", padx=(10, 4))
        self._bpm_min = ctk.StringVar()
        self._bpm_max = ctk.StringVar()
        self._bpm_min.trace_add("write", lambda *_: self._refresh_table())
        self._bpm_max.trace_add("write", lambda *_: self._refresh_table())
        ctk.CTkEntry(fbar, textvariable=self._bpm_min, width=55,
                      placeholder_text="min").pack(side="left", padx=2)
        ctk.CTkLabel(fbar, text="–").pack(side="left")
        ctk.CTkEntry(fbar, textvariable=self._bpm_max, width=55,
                      placeholder_text="max").pack(side="left", padx=2)

        # Row 2 — table + detail
        self.song_table = SongTable(self, on_select=self._on_select)
        self.song_table.grid(row=2, column=0, sticky="nsew", padx=(8, 4), pady=8)

        self.detail_panel = DetailPanel(self, conn=self.conn,
                                         on_download=self._on_download,
                                         on_uninstall=self._on_uninstall)
        self.detail_panel.grid(row=2, column=1, sticky="nsew", padx=(4, 8), pady=8)

        # Row 3 — status bar
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=3, column=0, columnspan=2,
                              sticky="ew", padx=8, pady=(0, 8))

    # ── Helpers ───────────────────────────────────────────────────────────
    def _filters(self) -> dict:
        f: dict = {
            "search":         self._search.get(),
            "definitive_only": self._def_only.get(),
        }
        if self._source.get() != "All Sources":
            f["source"] = self._source.get()
        if self._genre.get():
            f["genre"] = self._genre.get()
        try:
            if self._bpm_min.get():
                f["bpm_min"] = int(self._bpm_min.get())
        except ValueError:
            pass
        try:
            if self._bpm_max.get():
                f["bpm_max"] = int(self._bpm_max.get())
        except ValueError:
            pass
        return f

    def _refresh_table(self):
        self.song_table.load(get_songs(self.conn, self._filters()))

    def _on_select(self, song: dict):
        self.detail_panel.show(song)

    # ── Refresh sources ───────────────────────────────────────────────────
    def _start_refresh(self):
        self._refresh_btn.configure(state="disabled", text="Refreshing…")
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _do_refresh(self):
        try:
            upsert_songs(self.conn, fetch_fucuco() + fetch_fsl())
            self.after(0, lambda: self._updated_lbl.configure(
                text=f"Updated {date.today().isoformat()}"))
            self.after(0, self._refresh_table)
        except Exception as exc:
            self.after(0, lambda: self.status_bar.set_error(str(exc)))
        finally:
            self.after(0, lambda: self._refresh_btn.configure(
                state="normal", text="Refresh Sources"))

    # ── Download / install ────────────────────────────────────────────────
    def _on_download(self, song: dict):
        self.status_bar.start_download(song["title"])
        threading.Thread(target=self._do_download, args=(song,), daemon=True).start()

    def _do_download(self, song: dict):
        result = download(
            song["link"],
            progress_cb=lambda p: self.after(0, lambda: self.status_bar.set_progress(p)),
        )
        if result.status == "ok":
            install_pairs(result, song["id"], song["artist"], INSTALL_DIR, self.conn)
            self.after(0, self._refresh_table)
            self.after(0, lambda: self.status_bar.set_done(song["title"]))
        elif result.status == "manual":
            self.after(0, lambda: self.detail_panel.show_manual_link(result.raw_url))
            self.after(0, self.status_bar.set_idle)
        else:
            self.after(0, lambda: self.status_bar.set_error(result.error_msg or "Unknown error"))

    def _on_uninstall(self, song: dict):
        uninstall(song["id"], INSTALL_DIR, self.conn)
        self._refresh_table()
        updated = get_songs(self.conn, {"search": song["title"]})
        self.detail_panel.show(updated[0] if updated else {})
```

- [ ] **Step 5: Run smoke test**

```powershell
pytest tests\test_gui_smoke.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add gui\main_window.py gui\song_table.py gui\detail_panel.py gui\status_bar.py tests\test_gui_smoke.py
git commit -m "feat: GUI skeleton, main window with search/filter bar and layout"
```

---

### Task 8: Song table widget

**Files:**
- Modify: `gui\song_table.py`

- [ ] **Step 1: Replace stub with full implementation**

Replace `gui\song_table.py`:

```python
import customtkinter as ctk
from tkinter import ttk

COLUMNS = [
    ("status",     "Status",     55),
    ("artist",     "Artist",     160),
    ("title",      "Title",      200),
    ("creator",    "Creator",    120),
    ("bpm",        "BPM",        50),
    ("key",        "Key",        90),
    ("genre",      "Genre",      100),
    ("year",       "Year",       50),
    ("source",     "Source",     95),
    ("definitive", "Definitive", 75),
]


class SongTable(ctk.CTkFrame):
    def __init__(self, master, on_select=None, **kwargs):
        super().__init__(master, **kwargs)
        self._on_select = on_select
        self._rows: list[dict] = []
        self._sort_col = "artist"
        self._sort_asc = True
        self._build()

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2b2b2b", foreground="white",
                         fieldbackground="#2b2b2b", rowheight=24, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#1f538d",
                         foreground="white", font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", "#1f538d")])

        cols = [c[0] for c in COLUMNS]
        self._tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="browse")
        for col_id, label, width in COLUMNS:
            self._tree.heading(col_id, text=label,
                                command=lambda c=col_id: self._toggle_sort(c))
            self._tree.column(col_id, width=width, minwidth=40)

        vsb = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self._tree.tag_configure("installed", background="#1a3a2a")
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def load(self, rows: list[dict]):
        self._rows = rows
        self._tree.delete(*self._tree.get_children())
        for r in rows:
            values = (
                "✓" if r.get("pak_path") else "",
                r.get("artist", ""),
                r.get("title", ""),
                r.get("creator", ""),
                r.get("bpm", ""),
                r.get("key", ""),
                r.get("genre", ""),
                r.get("year", ""),
                r.get("source", ""),
                "★" if r.get("is_definitive") else "",
            )
            tag = "installed" if r.get("pak_path") else ""
            self._tree.insert("", "end", iid=str(r["id"]), values=values, tags=(tag,))

    def _toggle_sort(self, col: str):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col, self._sort_asc = col, True
        self._rows.sort(key=lambda r: (r.get(col) or ""), reverse=not self._sort_asc)
        self.load(self._rows)

    def _on_tree_select(self, _event):
        sel = self._tree.selection()
        if not sel or not self._on_select:
            return
        song = next((r for r in self._rows if str(r["id"]) == sel[0]), None)
        if song:
            self._on_select(song)
```

- [ ] **Step 2: Run smoke test**

```powershell
pytest tests\test_gui_smoke.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```powershell
git add gui\song_table.py
git commit -m "feat: song table — sortable columns, installed badge, definitive star"
```

---

### Task 9: Detail panel widget

**Files:**
- Modify: `gui\detail_panel.py`

- [ ] **Step 1: Replace stub with full implementation**

Replace `gui\detail_panel.py`:

```python
import webbrowser
import sqlite3
import customtkinter as ctk

_FIELDS = [
    ("artist",        "Artist"),
    ("title",         "Title"),
    ("creator",       "Creator"),
    ("bpm",           "BPM"),
    ("key",           "Key"),
    ("genre",         "Genre"),
    ("year",          "Year"),
    ("source",        "Source"),
    ("de_status",     "DE Status"),
    ("complete",      "Complete"),
    ("complete_notes","Notes"),
    ("origin",        "Origin"),
    ("stream_opt",    "Stream-Opt"),
]


class DetailPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, conn: sqlite3.Connection,
                 on_download=None, on_uninstall=None, **kwargs):
        super().__init__(master, **kwargs)
        self._conn = conn
        self._on_download = on_download
        self._on_uninstall = on_uninstall
        self._song: dict | None = None
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self._value_labels: dict[str, ctk.CTkLabel] = {}

        for i, (field, label) in enumerate(_FIELDS):
            ctk.CTkLabel(self, text=f"{label}:", anchor="w",
                          font=ctk.CTkFont(weight="bold")).grid(
                row=i, column=0, sticky="nw", padx=(10, 4), pady=(4, 0))
            lbl = ctk.CTkLabel(self, text="—", anchor="w", wraplength=220, justify="left")
            lbl.grid(row=i, column=1, sticky="w", padx=4, pady=(4, 0))
            self._value_labels[field] = lbl

        base = len(_FIELDS)

        ctk.CTkLabel(self, text="Link:", anchor="w",
                      font=ctk.CTkFont(weight="bold")).grid(
            row=base, column=0, sticky="nw", padx=(10, 4), pady=(4, 0))
        self._link_btn = ctk.CTkButton(self, text="—", anchor="w", width=220,
                                        fg_color="transparent", text_color="#6ab0f5",
                                        command=self._open_link)
        self._link_btn.grid(row=base, column=1, sticky="w", padx=4)

        self._path_lbl = ctk.CTkLabel(self, text="", anchor="w",
                                       text_color="#aaaaaa", wraplength=240, justify="left")
        self._path_lbl.grid(row=base + 1, column=0, columnspan=2, sticky="w", padx=10, pady=(2, 8))

        self._dl_btn = ctk.CTkButton(self, text="Download & Install", command=self._download)
        self._dl_btn.grid(row=base + 2, column=0, columnspan=2, sticky="ew", padx=10, pady=4)

        self._un_btn = ctk.CTkButton(self, text="Uninstall",
                                      fg_color="#7d1a1a", hover_color="#a32020",
                                      command=self._uninstall)
        self._un_btn.grid(row=base + 3, column=0, columnspan=2, sticky="ew", padx=10, pady=4)

        self._manual_lbl = ctk.CTkLabel(
            self, text="", text_color="#f4a261", wraplength=240, justify="left")
        self._manual_lbl.grid(row=base + 4, column=0, columnspan=2,
                               sticky="w", padx=10, pady=(4, 0))

        self._sync_buttons()

    def show(self, song: dict):
        self._song = song
        self._manual_lbl.configure(text="")
        for field, lbl in self._value_labels.items():
            val = song.get(field)
            if field == "stream_opt":
                text = "Yes" if val else "No"
            elif field == "complete":
                text = {"D": "Definitive", "C": "Complete"}.get(str(val or ""), str(val or "—"))
            else:
                text = str(val) if val not in (None, "") else "—"
            lbl.configure(text=text)

        link = song.get("link", "")
        self._link_btn.configure(text=(link[:38] + "…") if len(link) > 38 else link)
        self._path_lbl.configure(
            text=f"Installed: {song['pak_path']}" if song.get("pak_path") else "")
        self._sync_buttons()

    def show_manual_link(self, url: str):
        self._manual_lbl.configure(
            text="Manual download required.\nClick the link above to open in browser.")

    def _sync_buttons(self):
        if not self._song:
            self._dl_btn.configure(state="disabled")
            self._un_btn.configure(state="disabled")
            return
        installed = bool(self._song.get("pak_path"))
        self._dl_btn.configure(state="disabled" if installed else "normal")
        self._un_btn.configure(state="normal" if installed else "disabled")

    def _open_link(self):
        if self._song:
            webbrowser.open(self._song.get("link", ""))

    def _download(self):
        if self._song and self._on_download:
            self._dl_btn.configure(state="disabled")
            self._on_download(self._song)

    def _uninstall(self):
        if self._song and self._on_uninstall:
            self._on_uninstall(self._song)
```

- [ ] **Step 2: Run smoke test**

```powershell
pytest tests\test_gui_smoke.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```powershell
git add gui\detail_panel.py
git commit -m "feat: detail panel — metadata, download/uninstall buttons, manual fallback notice"
```

---

### Task 10: Status bar

**Files:**
- Modify: `gui\status_bar.py`

- [ ] **Step 1: Replace stub with full implementation**

Replace `gui\status_bar.py`:

```python
import customtkinter as ctk


class StatusBar(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, height=36, **kwargs)
        self.grid_columnconfigure(1, weight=1)

        self._lbl = ctk.CTkLabel(self, text="Ready", anchor="w")
        self._lbl.grid(row=0, column=0, padx=10, sticky="w")

        self._bar = ctk.CTkProgressBar(self, width=200)
        self._bar.set(0)
        self._bar.grid(row=0, column=1, padx=10, sticky="e")
        self._bar.grid_remove()

    def start_download(self, title: str):
        self._lbl.configure(text=f"Downloading: {title}", text_color="white")
        self._bar.set(0)
        self._bar.grid()

    def set_progress(self, value: float):
        self._bar.set(max(0.0, min(1.0, value)))

    def set_done(self, title: str):
        self._lbl.configure(text=f"Installed: {title}", text_color="#52b788")
        self._bar.set(1.0)
        self.after(3000, self.set_idle)

    def set_error(self, msg: str):
        self._lbl.configure(text=f"Error: {msg}", text_color="#e76f51")
        self._bar.grid_remove()

    def set_idle(self):
        self._lbl.configure(text="Ready", text_color="white")
        self._bar.grid_remove()
        self._bar.set(0)
```

- [ ] **Step 2: Run smoke test**

```powershell
pytest tests\test_gui_smoke.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit**

```powershell
git add gui\status_bar.py
git commit -m "feat: status bar — progress, done, error, idle states"
```

---

### Task 11: Entry point and full integration

**Files:**
- Create: `app.py`

- [ ] **Step 1: Create app.py**

Create `app.py`:

```python
from gui.main_window import FuserApp

if __name__ == "__main__":
    app = FuserApp()
    app.mainloop()
```

- [ ] **Step 2: Run the full test suite**

```powershell
pytest tests\ -v
```

Expected: All tests PASS. Count should be 34+.

- [ ] **Step 3: Launch the app**

```powershell
python app.py
```

Expected: A 1200×800 dark-themed window opens. Search bar and filter row are visible across the top. An empty table fills the left two-thirds. A blank detail panel occupies the right. Status bar reads "Ready". No crash on startup.

- [ ] **Step 4: Smoke-test Refresh Sources**

Click "Refresh Sources". The button should grey out, change to "Refreshing…", then return to normal. The table should populate with songs from all three fucuco tabs. The "Updated YYYY-MM-DD" label should appear beside the button.

- [ ] **Step 5: Commit**

```powershell
git add app.py
git commit -m "feat: entry point — python app.py launches the manager"
```
