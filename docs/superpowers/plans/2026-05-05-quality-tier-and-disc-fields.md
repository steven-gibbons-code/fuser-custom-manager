# Quality Tier and Disc Fields Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a four-tier quality classification (Official/Definitive/Complete/Other) as a table column, store disc instrument fields, and surface both in the UI.

**Architecture:** `derive_quality` in `db.py` computes the tier from stored fields during `upsert_songs`; new columns are added via non-destructive `ALTER TABLE` migration preserving installed records. Source fetcher adds `disc1–4` and `download_type` to normalised rows. The table replaces the Definitive column with Quality; the detail panel gains four disc rows.

**Tech Stack:** Python 3.11+, sqlite3, customtkinter, existing project stack.

---

## File Map

```
db.py                    — derive_quality helper, schema, migration, upsert update
sources/fucuco.py        — disc1–4, download_type in normalise_row
gui/song_table.py        — replace definitive column with quality
gui/detail_panel.py      — add disc1–4 to _FIELDS
tests/test_db.py         — tests for derive_quality, migration, new fields in upsert
tests/test_fucuco.py     — tests for disc and download_type in normalise_row
```

---

### Task 1: derive_quality + schema + migration in db.py

**Files:**
- Modify: `db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write failing tests for derive_quality and column migration**

Add to the end of `tests/test_db.py`:

```python
from db import derive_quality

@pytest.mark.parametrize("download_type,complete,de_status,notes,expected", [
    ("DLC",          "D", "",          "",           "Official"),
    ("Base Game",    "C", "",          "",           "Official"),
    ("Diamond Shop", "",  "",          "",           "Official"),
    ("https://drive.google.com/file/d/abc", "D", "", "", "Definitive"),
    ("",             "D", "",          "",           "Definitive"),
    ("",             "C", "Eligible",  "",           "Definitive"),
    ("",             "C", "",          "",           "Definitive"),
    ("",             "C", "",          "Wrong notes","Complete"),
    ("",             "C", "Not eligible", "",        "Complete"),
    ("",             "",  "",          "",           "Other"),
    ("",             "",  "Eligible",  "",           "Other"),
])
def test_derive_quality(download_type, complete, de_status, notes, expected):
    song = {
        "download_type": download_type, "complete": complete,
        "de_status": de_status, "complete_notes": notes,
    }
    assert derive_quality(song) == expected

def test_schema_has_new_columns(tmp_path):
    conn = init_db(tmp_path / "test.db")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(songs)").fetchall()}
    for col in ("disc1", "disc2", "disc3", "disc4", "download_type", "quality"):
        assert col in cols, f"Missing column: {col}"

def test_upsert_sets_quality(tmp_path):
    conn = init_db(tmp_path / "test.db")
    song = {**SONG, "download_type": "DLC", "disc1": "Drums", "disc2": "Vocals",
            "disc3": None, "disc4": None}
    upsert_songs(conn, [song])
    row = get_songs(conn, {})[0]
    assert row["quality"] == "Official"
    assert row["disc1"] == "Drums"
    assert row["disc2"] == "Vocals"

def test_upsert_quality_definitive(tmp_path):
    conn = init_db(tmp_path / "test.db")
    song = {**SONG, "download_type": "", "complete": "D"}
    upsert_songs(conn, [song])
    assert get_songs(conn, {})[0]["quality"] == "Definitive"

def test_upsert_quality_defaults_for_legacy_song(tmp_path):
    """upsert_songs handles songs without disc/download_type keys (backwards compat)."""
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG])  # SONG has no disc1–4 or download_type
    row = get_songs(conn, {})[0]
    assert row["quality"] in ("Official", "Definitive", "Complete", "Other")

def test_migrate_adds_columns_to_existing_schema(tmp_path):
    """Existing DB without quality/disc columns gets them added non-destructively."""
    import sqlite3 as _sql
    old_schema = """
    CREATE TABLE songs (
        id INTEGER PRIMARY KEY, source TEXT NOT NULL, artist TEXT, title TEXT,
        creator TEXT, genre TEXT, year INTEGER, bpm INTEGER, key TEXT,
        de_status TEXT, complete TEXT, complete_notes TEXT, stream_opt INTEGER DEFAULT 0,
        origin TEXT, link TEXT, link_host TEXT, last_seen TEXT, UNIQUE(source, link)
    );
    CREATE TABLE installed (
        id INTEGER PRIMARY KEY,
        song_id INTEGER UNIQUE REFERENCES songs(id) ON DELETE CASCADE,
        pak_path TEXT NOT NULL, sig_path TEXT, installed_at TEXT NOT NULL
    );
    """
    db_path = tmp_path / "old.db"
    old = _sql.connect(str(db_path))
    old.executescript(old_schema)
    old.close()
    conn = init_db(db_path)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(songs)").fetchall()}
    for col in ("disc1", "disc2", "disc3", "disc4", "download_type", "quality"):
        assert col in cols
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests\test_db.py -v -k "derive_quality or schema_has or upsert_sets or migrate"
```

Expected: FAIL — `ImportError: cannot import name 'derive_quality' from 'db'`

- [ ] **Step 3: Update SCHEMA in db.py to include new columns**

Replace the SCHEMA constant (lines 8–37):

```python
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
    disc1          TEXT,
    disc2          TEXT,
    disc3          TEXT,
    disc4          TEXT,
    download_type  TEXT,
    quality        TEXT,
    UNIQUE(source, link)
);

CREATE TABLE IF NOT EXISTS installed (
    id           INTEGER PRIMARY KEY,
    song_id      INTEGER UNIQUE REFERENCES songs(id) ON DELETE CASCADE,
    pak_path     TEXT NOT NULL,
    sig_path     TEXT,
    installed_at TEXT NOT NULL
);
"""
```

- [ ] **Step 4: Add derive_quality helper and _migrate_add_columns after the _IS_DEFINITIVE constant**

Insert after the `_IS_DEFINITIVE` block (after line 48):

```python
def derive_quality(song: dict) -> str:
    dt = (song.get("download_type") or "").strip()
    if dt and "://" not in dt and not dt.lower().startswith("http"):
        return "Official"
    c     = (song.get("complete")       or "").strip()
    de    = (song.get("de_status")      or "").strip()
    notes = (song.get("complete_notes") or "").strip()
    is_def = (
        c == "D"
        or (de == "Eligible" and c == "C")
        or (not de and c == "C" and not notes)
    )
    if is_def:
        return "Definitive"
    if c == "C":
        return "Complete"
    return "Other"


def _migrate_add_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(songs)").fetchall()}
    new_cols = [
        ("disc1",         "TEXT"),
        ("disc2",         "TEXT"),
        ("disc3",         "TEXT"),
        ("disc4",         "TEXT"),
        ("download_type", "TEXT"),
        ("quality",       "TEXT"),
    ]
    for col_name, col_type in new_cols:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE songs ADD COLUMN {col_name} {col_type}")
    conn.commit()
```

- [ ] **Step 5: Update init_db to call _migrate_add_columns**

Replace `init_db` (lines 61–71):

```python
def init_db(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if _needs_migration(conn):
        conn.executescript("DROP TABLE IF EXISTS installed; DROP TABLE IF EXISTS songs;")
    conn.executescript(SCHEMA)
    _migrate_add_columns(conn)
    conn.commit()
    return conn
```

- [ ] **Step 6: Update upsert_songs to set quality and default new fields**

Replace `upsert_songs` (lines 74–90):

```python
def upsert_songs(conn: sqlite3.Connection, songs: list[dict]) -> None:
    enriched = []
    for s in songs:
        s = dict(s)
        s.setdefault("disc1", None)
        s.setdefault("disc2", None)
        s.setdefault("disc3", None)
        s.setdefault("disc4", None)
        s.setdefault("download_type", None)
        s["quality"] = derive_quality(s)
        enriched.append(s)
    conn.executemany("""
        INSERT INTO songs (source, artist, title, creator, genre, year, bpm, key,
                           de_status, complete, complete_notes, stream_opt, origin,
                           link, link_host, last_seen,
                           disc1, disc2, disc3, disc4, download_type, quality)
        VALUES (:source, :artist, :title, :creator, :genre, :year, :bpm, :key,
                :de_status, :complete, :complete_notes, :stream_opt, :origin,
                :link, :link_host, :last_seen,
                :disc1, :disc2, :disc3, :disc4, :download_type, :quality)
        ON CONFLICT(source, link) DO UPDATE SET
            artist=excluded.artist, title=excluded.title,
            creator=excluded.creator, genre=excluded.genre, year=excluded.year,
            bpm=excluded.bpm, key=excluded.key, de_status=excluded.de_status,
            complete=excluded.complete, complete_notes=excluded.complete_notes,
            stream_opt=excluded.stream_opt, origin=excluded.origin,
            link_host=excluded.link_host, last_seen=excluded.last_seen,
            disc1=excluded.disc1, disc2=excluded.disc2,
            disc3=excluded.disc3, disc4=excluded.disc4,
            download_type=excluded.download_type, quality=excluded.quality
    """, enriched)
    conn.commit()
```

- [ ] **Step 7: Run all db tests**

```powershell
pytest tests\test_db.py -v
```

Expected: All tests PASS.

- [ ] **Step 8: Commit**

```powershell
git add db.py tests\test_db.py
git commit -m "feat: quality tier, disc fields, and non-destructive column migration in db"
```

---

### Task 2: disc fields and download_type in fucuco.py

**Files:**
- Modify: `sources/fucuco.py`
- Modify: `tests/test_fucuco.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_fucuco.py`:

```python
def test_normalise_includes_disc_fields():
    row = {
        "Artist": "Daft Punk", "Title": "Get Lucky", "Creator": "DJTest",
        "Disc 1 ": "Drums", "Disc 2 ": "Vocals", "Disc 3 ": "Sampler", "Disc 4 ": "",
        "Download": "Google Drive",
        "Link": "https://drive.google.com/file/d/abc",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["disc1"] == "Drums"
    assert r["disc2"] == "Vocals"
    assert r["disc3"] == "Sampler"
    assert r["disc4"] is None       # blank → None

def test_normalise_download_type_official():
    row = {
        "Artist": "Harmonix", "Title": "Base Song", "Creator": "Harmonix",
        "Download": "Base Game",
        "Link": "https://drive.google.com/file/d/xyz",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["download_type"] == "Base Game"

def test_normalise_download_type_url_passthrough():
    row = {
        "Artist": "A", "Title": "B", "Creator": "C",
        "Download": "https://drive.google.com/drive/folders/abc",
        "Link": "https://drive.google.com/file/d/def",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["download_type"] == "https://drive.google.com/drive/folders/abc"

def test_normalise_download_type_missing():
    row = {
        "Artist": "A", "Title": "B", "Creator": "C",
        "Link": "https://drive.google.com/file/d/ghi",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["download_type"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
pytest tests\test_fucuco.py -v -k "disc or download_type"
```

Expected: FAIL — `KeyError: 'disc1'`

- [ ] **Step 3: Add disc and download_type columns to normalise_row**

In `sources/fucuco.py`, inside `normalise_row`, add after `origin_col = _find(h, "Origin")` (line 81):

```python
    disc1_col    = _find(h, "Disc 1", "Disc 1 ")
    disc2_col    = _find(h, "Disc 2", "Disc 2 ")
    disc3_col    = _find(h, "Disc 3", "Disc 3 ")
    disc4_col    = _find(h, "Disc 4", "Disc 4 ")
    download_col = _find(h, "Download")
```

And update the return dict to include five new keys after `"origin"`:

```python
        "origin":         row.get(origin_col or "", "").strip() or None,
        "disc1":          row.get(disc1_col  or "", "").strip() or None,
        "disc2":          row.get(disc2_col  or "", "").strip() or None,
        "disc3":          row.get(disc3_col  or "", "").strip() or None,
        "disc4":          row.get(disc4_col  or "", "").strip() or None,
        "download_type":  row.get(download_col or "", "").strip() or None,
        "link":           link,
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
pytest tests\test_fucuco.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add sources\fucuco.py tests\test_fucuco.py
git commit -m "feat: disc1–4 and download_type fields in fucuco normalise_row"
```

---

### Task 3: Quality column in song table

**Files:**
- Modify: `gui/song_table.py`

- [ ] **Step 1: Replace COLUMNS definition and add quality abbreviation map**

In `gui/song_table.py`, replace the COLUMNS constant (lines 4–15) and add `_QUALITY_ABBR` above it:

```python
_QUALITY_ABBR = {"Official": "Off", "Definitive": "Def", "Complete": "Cmp"}

COLUMNS = [
    ("status",  "Status",  55),
    ("quality", "Quality", 45),
    ("artist",  "Artist",  160),
    ("title",   "Title",   200),
    ("creator", "Creator", 120),
    ("bpm",     "BPM",     50),
    ("key",     "Key",     90),
    ("genre",   "Genre",   100),
    ("year",    "Year",    50),
    ("source",  "Source",  95),
]
```

- [ ] **Step 2: Update the load() method to use quality instead of definitive**

In the `load` method, replace:

```python
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
```

with:

```python
            values = (
                "✓" if r.get("pak_path") else "",
                _QUALITY_ABBR.get(r.get("quality", ""), ""),
                r.get("artist", ""),
                r.get("title", ""),
                r.get("creator", ""),
                r.get("bpm", ""),
                r.get("key", ""),
                r.get("genre", ""),
                r.get("year", ""),
                r.get("source", ""),
            )
```

- [ ] **Step 3: Run smoke test**

```powershell
pytest tests\test_gui_smoke.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add gui\song_table.py
git commit -m "feat: replace definitive column with quality tier in song table"
```

---

### Task 4: Disc fields in detail panel

**Files:**
- Modify: `gui/detail_panel.py`

- [ ] **Step 1: Add disc fields to _FIELDS**

In `gui/detail_panel.py`, find `_FIELDS` and add four entries after `("origin", "Origin")`:

```python
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
    ("disc1",         "Disc 1"),
    ("disc2",         "Disc 2"),
    ("disc3",         "Disc 3"),
    ("disc4",         "Disc 4"),
    ("stream_opt",    "Stream-Opt"),
]
```

- [ ] **Step 2: Run smoke test**

```powershell
pytest tests\test_gui_smoke.py -v
```

Expected: PASS.

- [ ] **Step 3: Run the full test suite**

```powershell
pytest tests\ -v
```

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```powershell
git add gui\detail_panel.py
git commit -m "feat: disc 1–4 instrument fields in detail panel"
```
