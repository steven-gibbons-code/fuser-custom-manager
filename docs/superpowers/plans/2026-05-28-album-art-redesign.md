# Album Art Redesign: iTunes-First, Album-Level Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the per-song art system with iTunes-first album-level art that deduplicates files on disk and shows accurate album covers.

**Architecture:** A new `album_art` table keyed by `(artist, album)` stores one art record per unique album. Songs reference this via `album_art_id` FK. Art files are named `{album_art_id}.jpg`, so every song on the same album shares one file. iTunes Search API is the primary resolver (artist + title → album name + artwork URL), with GDrive as fallback and the existing gradient as placeholder.

**Tech Stack:** Python, SQLite (via `sqlite3`), PySide6 (Qt signals), `requests`, iTunes Search API (no auth)

---

## File Map

| File | Change |
|---|---|
| `db.py` | Add `album_art` table to SCHEMA; add `album_art_id` column migration + art file wipe; add `get_or_create_album_art`, `link_song_album_art`, `get_songs_pending_art`; update `count_pending_art`; remove `art_url` from `upsert_songs` |
| `sources/art_resolver.py` | Replace `musicbrainz_lookup` with `itunes_lookup`; update `bulk_resolve` to use album-level schema |
| `gui/workers.py` | Update `ParallelArtWorker` (new queries, iTunes resolver, album dedup, `progress` signal); update `SingleArtWorker`; update `ArtResolveWorker`/`ArtFetchWorker` |
| `gui/status_bar.py` | Add `start_art_resolve(total: int)` method |
| `gui/main_window.py` | Wire `worker.progress`; call `count_pending_art` + `start_art_resolve` before starting worker |
| `gui/song_delegate.py` | Change `_art_pixmap(song_id)` → `_art_pixmap(song: dict)`; load from `album_art_id` file path |
| `tests/test_db.py` | Tests for new helper functions and migration |
| `tests/test_art_resolver.py` | Rewrite for `itunes_lookup`; update `bulk_resolve` tests |
| `tests/test_workers.py` | Update `ParallelArtWorker` and `SingleArtWorker` tests for new schema |

---

## Task 1: DB Schema — album_art Table, album_art_id Column, Migration

**Files:**
- Modify: `db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing tests for new DB helpers**

Add to `tests/test_db.py`:

```python
from db import (init_db, upsert_songs, get_songs, mark_installed,
                mark_uninstalled, get_installed, get_setting, set_setting,
                count_pending_art, ART_DIR,
                get_or_create_album_art, link_song_album_art, get_songs_pending_art)

# Add alongside existing SONG fixture
SONG_FSL = {
    "source": "fusersoundlab", "artist": "Daft Punk", "title": "Get Lucky",
    "creator": "DJTest", "genre": "Pop", "year": 2013, "bpm": 116,
    "key": "A Minor", "de_status": "Eligible", "complete": "C",
    "complete_notes": "", "stream_opt": 1, "origin": None,
    "link": "https://fsl.com/1", "link_host": "fsl",
    "last_seen": "2026-05-28",
}


def test_album_art_table_created(conn):
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "album_art" in tables


def test_get_or_create_album_art_inserts_new(conn):
    art_id = get_or_create_album_art(conn, "Daft Punk", "Random Access Memories", "http://example.com/art.jpg")
    assert isinstance(art_id, int)
    row = conn.execute("SELECT artist, album, art_url FROM album_art WHERE id = ?", (art_id,)).fetchone()
    assert row[0] == "Daft Punk"
    assert row[1] == "Random Access Memories"
    assert row[2] == "http://example.com/art.jpg"


def test_get_or_create_album_art_returns_existing_id(conn):
    id1 = get_or_create_album_art(conn, "Daft Punk", "Random Access Memories", "http://example.com/art.jpg")
    id2 = get_or_create_album_art(conn, "Daft Punk", "Random Access Memories", "http://example.com/art.jpg")
    assert id1 == id2
    count = conn.execute("SELECT COUNT(*) FROM album_art").fetchone()[0]
    assert count == 1


def test_link_song_album_art(conn):
    upsert_songs(conn, [SONG])
    song_id = conn.execute("SELECT id FROM songs").fetchone()[0]
    art_id = get_or_create_album_art(conn, "Daft Punk", "RAM", "http://example.com/art.jpg")
    link_song_album_art(conn, song_id, art_id)
    row = conn.execute("SELECT album_art_id FROM songs WHERE id = ?", (song_id,)).fetchone()
    assert row[0] == art_id


def test_get_songs_pending_art_excludes_fsl(conn):
    upsert_songs(conn, [SONG, SONG_FSL])
    pending = get_songs_pending_art(conn)
    sources = {s["source"] for s in pending}
    assert "fusersoundlab" not in sources
    assert any(s["source"] == "fucuco_main" for s in pending)


def test_get_songs_pending_art_excludes_linked(conn):
    upsert_songs(conn, [SONG])
    song_id = conn.execute("SELECT id FROM songs WHERE source='fucuco_main'").fetchone()[0]
    art_id = get_or_create_album_art(conn, "Daft Punk", "RAM", "http://example.com/art.jpg")
    link_song_album_art(conn, song_id, art_id)
    pending = get_songs_pending_art(conn)
    ids = {s["id"] for s in pending}
    assert song_id not in ids


def test_count_pending_art_uses_album_art_id(conn):
    upsert_songs(conn, [SONG])
    assert count_pending_art(conn) == 1
    song_id = conn.execute("SELECT id FROM songs").fetchone()[0]
    art_id = get_or_create_album_art(conn, "Daft Punk", "RAM", "http://example.com/art.jpg")
    link_song_album_art(conn, song_id, art_id)
    assert count_pending_art(conn) == 0


def test_migration_wipes_old_art_files(tmp_path):
    # First init — no album_art_id column yet, simulate old art files
    import sqlite3
    old_db = tmp_path / "test.db"
    old_art_dir = tmp_path / "art"
    old_art_dir.mkdir()
    (old_art_dir / "1.jpg").write_bytes(b"OLD")
    (old_art_dir / "2.jpg").write_bytes(b"OLD")

    # Patch ART_DIR to our tmp art dir
    import db as db_mod
    original_art_dir = db_mod.ART_DIR
    db_mod.ART_DIR = old_art_dir
    try:
        conn = init_db(old_db)
        conn.close()
        # After migration, old files should be gone
        assert not (old_art_dir / "1.jpg").exists()
        assert not (old_art_dir / "2.jpg").exists()
    finally:
        db_mod.ART_DIR = original_art_dir
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_db.py::test_album_art_table_created tests/test_db.py::test_get_or_create_album_art_inserts_new tests/test_db.py::test_get_songs_pending_art_excludes_fsl -v
```

Expected: FAIL — `get_or_create_album_art` not defined, `album_art` table missing.

- [ ] **Step 3: Update `db.py` — add album_art to SCHEMA**

In `db.py`, add the `album_art` table to the SCHEMA constant (insert after the `songs` table block):

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
    submit_date    TEXT,
    UNIQUE(source, link)
);

CREATE TABLE IF NOT EXISTS album_art (
    id      INTEGER PRIMARY KEY,
    artist  TEXT NOT NULL,
    album   TEXT NOT NULL,
    art_url TEXT,
    UNIQUE(artist, album)
);

CREATE TABLE IF NOT EXISTS installed (
    id           INTEGER PRIMARY KEY,
    song_id      INTEGER UNIQUE REFERENCES songs(id) ON DELETE CASCADE,
    pak_path     TEXT NOT NULL,
    sig_path     TEXT,
    installed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""
```

- [ ] **Step 4: Update `_migrate_add_columns` to add `album_art_id` and wipe old art files**

Replace the existing `_migrate_add_columns` function in `db.py`:

```python
def _migrate_add_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(songs)").fetchall()}
    new_cols = [
        ("disc1",         "TEXT"),
        ("disc2",         "TEXT"),
        ("disc3",         "TEXT"),
        ("disc4",         "TEXT"),
        ("download_type", "TEXT"),
        ("quality",       "TEXT"),
        ("submit_date",   "TEXT"),
        ("art_url",       "TEXT"),
        ("album_art_id",  "INTEGER REFERENCES album_art(id)"),
    ]
    first_album_art_migration = "album_art_id" not in existing
    for col_name, col_type in new_cols:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE songs ADD COLUMN {col_name} {col_type}")
    conn.commit()

    if first_album_art_migration and ART_DIR.exists():
        for f in ART_DIR.glob("*.jpg"):
            try:
                f.unlink()
            except Exception:
                pass
```

- [ ] **Step 5: Add new helper functions to `db.py`**

Add these functions after `update_art_url`:

```python
def get_or_create_album_art(conn: sqlite3.Connection, artist: str, album: str, art_url: str) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO album_art (artist, album, art_url) VALUES (?, ?, ?)",
        (artist, album, art_url),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM album_art WHERE artist = ? AND album = ?",
        (artist, album),
    ).fetchone()[0]


def link_song_album_art(conn: sqlite3.Connection, song_id: int, album_art_id: int) -> None:
    conn.execute("UPDATE songs SET album_art_id = ? WHERE id = ?", (album_art_id, song_id))
    conn.commit()


def get_songs_pending_art(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, artist, title FROM songs "
        "WHERE album_art_id IS NULL AND source != 'fusersoundlab'"
    ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 6: Update `count_pending_art` in `db.py`**

Replace the existing `count_pending_art` function:

```python
def count_pending_art(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM songs WHERE album_art_id IS NULL AND source != 'fusersoundlab'"
    ).fetchone()[0]
```

- [ ] **Step 7: Remove `art_url` from `upsert_songs`**

In `upsert_songs`, remove all references to `art_url`. The updated function:

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
        s.setdefault("submit_date", None)
        s["quality"] = derive_quality(s)
        enriched.append(s)
    conn.executemany("""
        INSERT INTO songs (source, artist, title, creator, genre, year, bpm, key,
                           de_status, complete, complete_notes, stream_opt, origin,
                           link, link_host, last_seen,
                           disc1, disc2, disc3, disc4, download_type, quality, submit_date)
        VALUES (:source, :artist, :title, :creator, :genre, :year, :bpm, :key,
                :de_status, :complete, :complete_notes, :stream_opt, :origin,
                :link, :link_host, :last_seen,
                :disc1, :disc2, :disc3, :disc4, :download_type, :quality, :submit_date)
        ON CONFLICT(source, link) DO UPDATE SET
            artist=excluded.artist, title=excluded.title,
            creator=excluded.creator, genre=excluded.genre, year=excluded.year,
            bpm=excluded.bpm, key=excluded.key, de_status=excluded.de_status,
            complete=excluded.complete, complete_notes=excluded.complete_notes,
            stream_opt=excluded.stream_opt, origin=excluded.origin,
            link_host=excluded.link_host, last_seen=excluded.last_seen,
            disc1=excluded.disc1, disc2=excluded.disc2,
            disc3=excluded.disc3, disc4=excluded.disc4,
            download_type=excluded.download_type, quality=excluded.quality,
            submit_date=COALESCE(excluded.submit_date, submit_date)
    """, enriched)
    conn.commit()
```

- [ ] **Step 8: Run all new DB tests**

```
pytest tests/test_db.py -v
```

Expected: All pass. Fix any failures before continuing.

- [ ] **Step 9: Run the full test suite to catch regressions**

```
pytest tests/ -v --ignore=tests/test_workers.py --ignore=tests/test_art_resolver.py
```

Expected: All pass (workers and art_resolver tests will fail — handled in later tasks).

- [ ] **Step 10: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add album_art table, album_art_id column, and DB helpers"
```

---

## Task 2: iTunes Lookup — Replace musicbrainz_lookup

**Files:**
- Modify: `sources/art_resolver.py`
- Test: `tests/test_art_resolver.py`

- [ ] **Step 1: Write failing tests for `itunes_lookup`**

Replace the entire contents of `tests/test_art_resolver.py` with:

```python
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).parent.parent))

from sources.art_resolver import itunes_lookup


def _make_itunes_resp(results):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"results": results}
    return resp


def test_itunes_lookup_returns_album_and_url():
    result = [{"collectionName": "Random Access Memories", "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/abc/100x100bb.jpg"}]
    with patch("sources.art_resolver.requests.get", return_value=_make_itunes_resp(result)), \
         patch("sources.art_resolver.time.sleep"):
        album, url = itunes_lookup("Daft Punk", "Get Lucky")
    assert album == "Random Access Memories"
    assert "600x600bb" in url


def test_itunes_lookup_returns_none_when_no_results():
    with patch("sources.art_resolver.requests.get", return_value=_make_itunes_resp([])), \
         patch("sources.art_resolver.time.sleep"):
        result = itunes_lookup("Unknown Artist", "Unknown Track")
    assert result is None


def test_itunes_lookup_returns_none_when_non_200():
    resp = MagicMock()
    resp.status_code = 503
    with patch("sources.art_resolver.requests.get", return_value=resp), \
         patch("sources.art_resolver.time.sleep"):
        result = itunes_lookup("Daft Punk", "Get Lucky")
    assert result is None


def test_itunes_lookup_returns_none_on_network_error():
    with patch("sources.art_resolver.requests.get", side_effect=Exception("timeout")), \
         patch("sources.art_resolver.time.sleep"):
        result = itunes_lookup("Daft Punk", "Get Lucky")
    assert result is None


def test_itunes_lookup_returns_none_when_missing_album():
    result = [{"artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/abc/100x100bb.jpg"}]
    with patch("sources.art_resolver.requests.get", return_value=_make_itunes_resp(result)), \
         patch("sources.art_resolver.time.sleep"):
        assert itunes_lookup("Daft Punk", "Get Lucky") is None


def test_itunes_lookup_returns_none_when_missing_artwork():
    result = [{"collectionName": "Random Access Memories"}]
    with patch("sources.art_resolver.requests.get", return_value=_make_itunes_resp(result)), \
         patch("sources.art_resolver.time.sleep"):
        assert itunes_lookup("Daft Punk", "Get Lucky") is None


def test_itunes_throttle_serializes_calls():
    import threading, time
    from sources.art_resolver import _itunes_throttle
    import sources.art_resolver as ar
    original = ar._ITUNES_LAST_CALL
    ar._ITUNES_LAST_CALL = 0.0
    try:
        call_times = []
        def call():
            _itunes_throttle()
            call_times.append(time.time())
        threads = [threading.Thread(target=call) for _ in range(3)]
        for t in threads: t.start()
        for t in threads: t.join()
        call_times.sort()
        assert call_times[1] - call_times[0] >= 0.3
        assert call_times[2] - call_times[1] >= 0.3
    finally:
        ar._ITUNES_LAST_CALL = original


# --- bulk_resolve tests ---
from db import init_db, upsert_songs
from sources.art_resolver import bulk_resolve

_SONG = {
    "source": "fucuco_main", "artist": "Daft Punk", "title": "Get Lucky",
    "creator": "", "genre": "", "year": 2013, "bpm": 116, "key": "",
    "de_status": "", "complete": "", "complete_notes": "", "stream_opt": 0,
    "origin": None, "disc1": None, "disc2": None, "disc3": None, "disc4": None,
    "download_type": None, "submit_date": None,
    "link": "https://drive.google.com/file/d/abc", "link_host": "gdrive",
    "last_seen": "2026-05-28",
}

_FSL_SONG = {
    **_SONG,
    "source": "fusersoundlab",
    "link": "https://fsl.com/1",
}


def test_bulk_resolve_sets_album_art_id_via_itunes(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [_SONG])
    song_id = conn.execute("SELECT id FROM songs").fetchone()[0]

    with patch("sources.art_resolver.itunes_lookup", return_value=("RAM", "http://itunes.com/art.jpg")), \
         patch("sources.art_resolver.requests.get") as mock_dl:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"FAKEIMAGE"
        mock_dl.return_value = mock_resp
        bulk_resolve(conn, art_dir=tmp_path / "art")

    row = conn.execute("SELECT album_art_id FROM songs WHERE id = ?", (song_id,)).fetchone()
    assert row[0] is not None
    art_row = conn.execute("SELECT album FROM album_art WHERE id = ?", (row[0],)).fetchone()
    assert art_row[0] == "RAM"


def test_bulk_resolve_skips_fsl_songs(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [_FSL_SONG])

    with patch("sources.art_resolver.itunes_lookup") as mock_itunes:
        bulk_resolve(conn, art_dir=tmp_path / "art")
        mock_itunes.assert_not_called()


def test_bulk_resolve_falls_back_to_gdrive(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [_SONG])
    song_id = conn.execute("SELECT id FROM songs").fetchone()[0]

    with patch("sources.art_resolver.itunes_lookup", return_value=None), \
         patch("sources.art_resolver.gdrive_art_lookup", return_value="http://gdrive.com/art.jpg"), \
         patch("sources.art_resolver.requests.get") as mock_dl:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"FAKEIMAGE"
        mock_dl.return_value = mock_resp
        bulk_resolve(conn, art_dir=tmp_path / "art")

    row = conn.execute("SELECT album_art_id FROM songs WHERE id = ?", (song_id,)).fetchone()
    assert row[0] is not None
    art_row = conn.execute("SELECT album FROM album_art WHERE id = ?", (row[0],)).fetchone()
    assert art_row[0] == "__artist__"


def test_bulk_resolve_leaves_null_when_all_sources_fail(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [_SONG])
    song_id = conn.execute("SELECT id FROM songs").fetchone()[0]

    with patch("sources.art_resolver.itunes_lookup", return_value=None), \
         patch("sources.art_resolver.gdrive_art_lookup", return_value=None):
        bulk_resolve(conn, art_dir=tmp_path / "art")

    row = conn.execute("SELECT album_art_id FROM songs WHERE id = ?", (song_id,)).fetchone()
    assert row[0] is None


def test_bulk_resolve_deduplicates_album_downloads(tmp_path):
    """Two songs on the same album should produce one album_art row and one file."""
    conn = init_db(tmp_path / "test.db")
    song_a = {**_SONG, "title": "Get Lucky"}
    song_b = {**_SONG, "title": "Lose Yourself to Dance", "link": "https://drive.google.com/file/d/xyz"}
    upsert_songs(conn, [song_a, song_b])

    download_count = [0]
    def fake_download(url, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"IMG"
        download_count[0] += 1
        return resp

    with patch("sources.art_resolver.itunes_lookup", return_value=("RAM", "http://itunes.com/art.jpg")), \
         patch("sources.art_resolver.requests.get", side_effect=fake_download):
        bulk_resolve(conn, art_dir=tmp_path / "art")

    # Only one download should have happened (file exists after first song)
    assert download_count[0] == 1
    # Both songs should point to the same album_art row
    rows = conn.execute("SELECT album_art_id FROM songs WHERE source='fucuco_main'").fetchall()
    ids = [r[0] for r in rows]
    assert ids[0] == ids[1]
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_art_resolver.py -v
```

Expected: FAIL — `itunes_lookup` not defined.

- [ ] **Step 3: Rewrite `sources/art_resolver.py`**

Replace the entire file:

```python
import time
import sqlite3
import threading
import requests

from db import (
    update_art_url, get_songs_pending_art,
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
```

- [ ] **Step 4: Run art resolver tests**

```
pytest tests/test_art_resolver.py -v
```

Expected: All pass. Fix any failures before continuing.

- [ ] **Step 5: Commit**

```bash
git add sources/art_resolver.py tests/test_art_resolver.py
git commit -m "feat: replace musicbrainz_lookup with itunes_lookup, update bulk_resolve"
```

---

## Task 3: ParallelArtWorker — New Schema, iTunes Resolver, Progress Signal

**Files:**
- Modify: `gui/workers.py`
- Test: `tests/test_workers.py`

- [ ] **Step 1: Write failing tests for updated ParallelArtWorker**

Replace the `ParallelArtWorker`-related tests in `tests/test_workers.py` (lines 279–443). The new tests should work with the album_art schema:

```python
def test_parallel_art_worker_resolves_via_itunes_and_downloads(qtbot, tmp_path):
    import sqlite3
    from gui.workers import ParallelArtWorker

    art_dir = tmp_path / "art"
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE album_art (
            id INTEGER PRIMARY KEY, artist TEXT NOT NULL, album TEXT NOT NULL,
            art_url TEXT, UNIQUE(artist, album)
        );
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            album_art_id INTEGER, source TEXT
        );
        INSERT INTO songs VALUES (1, 'Daft Punk', 'Get Lucky', NULL, 'fucuco');
    """)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"IMAGEDATA"
    received = []
    progress_vals = []

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.itunes_lookup", return_value=("RAM", "http://itunes.com/art.jpg")), \
         patch("gui.workers.requests.get", return_value=mock_resp), \
         patch("gui.workers.get_or_create_album_art", wraps=lambda c, ar, al, u: 1) as mock_create, \
         patch("gui.workers.link_song_album_art") as mock_link:
        worker = ParallelArtWorker(conn, n_resolve=1, n_download=1)
        worker.art_ready.connect(lambda sid: received.append(sid))
        worker.progress.connect(lambda v: progress_vals.append(v))
        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.start()

    assert 1 in received
    mock_link.assert_called()
    assert any(v > 0 for v in progress_vals)


def test_parallel_art_worker_falls_back_to_gdrive(qtbot, tmp_path):
    import sqlite3
    from gui.workers import ParallelArtWorker

    art_dir = tmp_path / "art"
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE album_art (
            id INTEGER PRIMARY KEY, artist TEXT NOT NULL, album TEXT NOT NULL,
            art_url TEXT, UNIQUE(artist, album)
        );
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            album_art_id INTEGER, source TEXT
        );
        INSERT INTO songs VALUES (1, 'Daft Punk', 'Get Lucky', NULL, 'fucuco');
    """)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"IMAGEDATA"
    received = []

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.itunes_lookup", return_value=None), \
         patch("gui.workers.gdrive_art_lookup", return_value="http://gdrive.com/art.jpg"), \
         patch("gui.workers.requests.get", return_value=mock_resp), \
         patch("gui.workers.get_or_create_album_art", return_value=1), \
         patch("gui.workers.link_song_album_art"):
        worker = ParallelArtWorker(conn, n_resolve=1, n_download=1)
        worker.art_ready.connect(lambda sid: received.append(sid))
        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.start()

    assert 1 in received


def test_parallel_art_worker_emits_finished_with_no_pending(qtbot, tmp_path):
    import sqlite3
    from gui.workers import ParallelArtWorker

    art_dir = tmp_path / "art"
    art_dir.mkdir()
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE album_art (
            id INTEGER PRIMARY KEY, artist TEXT NOT NULL, album TEXT NOT NULL,
            art_url TEXT, UNIQUE(artist, album)
        );
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            album_art_id INTEGER, source TEXT
        );
        INSERT INTO album_art VALUES (5, 'Daft Punk', 'RAM', 'http://itunes.com/art.jpg');
        INSERT INTO songs VALUES (1, 'Daft Punk', 'Get Lucky', 5, 'fucuco');
    """)
    (art_dir / "5.jpg").write_bytes(b"CACHED")

    with patch("gui.workers.ART_DIR", art_dir):
        worker = ParallelArtWorker(conn, n_resolve=1, n_download=1)
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()


def test_parallel_art_worker_stop_terminates_gracefully(qtbot, tmp_path):
    import sqlite3
    from gui.workers import ParallelArtWorker

    art_dir = tmp_path / "art"
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE album_art (
            id INTEGER PRIMARY KEY, artist TEXT NOT NULL, album TEXT NOT NULL,
            art_url TEXT, UNIQUE(artist, album)
        );
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            album_art_id INTEGER, source TEXT
        );
        INSERT INTO songs VALUES (1, 'Artist A', 'Song X', NULL, 'fucuco');
    """)

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.itunes_lookup", return_value=None), \
         patch("gui.workers.gdrive_art_lookup", return_value=None):
        worker = ParallelArtWorker(conn, n_resolve=1, n_download=1)
        worker.start()
        worker.stop()
        with qtbot.waitSignal(worker.finished, timeout=5000):
            pass

    assert worker._cancel.is_set()


def test_parallel_art_worker_skips_existing_file(qtbot, tmp_path):
    """Song with existing album_art_id and existing file should emit art_ready without downloading."""
    import sqlite3
    from gui.workers import ParallelArtWorker

    art_dir = tmp_path / "art"
    art_dir.mkdir()
    (art_dir / "3.jpg").write_bytes(b"CACHED")

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE album_art (
            id INTEGER PRIMARY KEY, artist TEXT NOT NULL, album TEXT NOT NULL,
            art_url TEXT, UNIQUE(artist, album)
        );
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            album_art_id INTEGER, source TEXT
        );
        INSERT INTO album_art VALUES (3, 'Artist C', 'Album C', 'http://ex.com/3.jpg');
        INSERT INTO songs VALUES (2, 'Artist C', 'Song Z', 3, 'fucuco');
    """)

    received = []
    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.requests.get") as mock_get:
        worker = ParallelArtWorker(conn, n_resolve=1, n_download=1)
        worker.art_ready.connect(lambda sid: received.append(sid))
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()
        mock_get.assert_not_called()

    assert 2 in received
```

- [ ] **Step 2: Run new tests to verify they fail**

```
pytest tests/test_workers.py::test_parallel_art_worker_resolves_via_itunes_and_downloads tests/test_workers.py::test_parallel_art_worker_falls_back_to_gdrive -v
```

Expected: FAIL — `progress` signal missing, workers use old schema.

- [ ] **Step 3: Rewrite `ParallelArtWorker` in `gui/workers.py`**

Replace the existing `ParallelArtWorker` class (lines 76–221):

```python
class ParallelArtWorker(QThread):
    """Concurrent art resolve + download worker with visible-window prioritization.

    Resolve pool (iTunes-first, GDrive fallback) feeds a download pool.
    Call prioritize() with visible song IDs at any time to process those first.
    """

    art_ready = Signal(int)
    finished = Signal()
    status = Signal(str)
    progress = Signal(float)

    def __init__(self, conn, n_resolve: int = 5, n_download: int = 10, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._n_resolve = n_resolve
        self._n_download = n_download
        self._cancel = threading.Event()
        self._pq = ArtPriorityQueue()
        self._dl_q: queue.Queue = queue.Queue()
        self._songs_by_id: dict[int, dict] = {}
        self._write_lock = threading.Lock()

    @Slot(list)
    def prioritize(self, song_ids: list) -> None:
        self._pq.promote(song_ids, self._songs_by_id)

    def stop(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        ART_DIR.mkdir(parents=True, exist_ok=True)
        self.status.emit("Resolving art…")

        rows = self._conn.execute(
            "SELECT id, artist, title FROM songs "
            "WHERE album_art_id IS NULL AND source != 'fusersoundlab'"
        ).fetchall()
        pending_resolve = [dict(r) for r in rows]

        rows2 = self._conn.execute(
            "SELECT s.id, s.album_art_id, a.art_url FROM songs s "
            "JOIN album_art a ON a.id = s.album_art_id "
            "WHERE s.album_art_id IS NOT NULL"
        ).fetchall()
        pending_download = [
            {"id": r["id"], "album_art_id": r["album_art_id"], "art_url": r["art_url"]}
            for r in rows2
            if not (ART_DIR / f"{r['album_art_id']}.jpg").exists()
        ]

        if not pending_resolve and not pending_download:
            self.finished.emit()
            return

        total = len(pending_resolve) + len(pending_download)

        for s in pending_resolve:
            self._songs_by_id[s["id"]] = s

        for s in pending_resolve:
            self._pq.put(1, s)
        for _ in range(self._n_resolve):
            self._pq.put_sentinel()

        for s in pending_download:
            self._dl_q.put((s["id"], s["album_art_id"], s["art_url"]))

        result_q: queue.Queue = queue.Queue()
        completed = [0]
        sentinels_sent = [False]

        cancel = self._cancel
        pq = self._pq
        dl_q = self._dl_q
        write_lock = self._write_lock
        conn = self._conn

        def resolve_loop() -> None:
            while not cancel.is_set():
                song = pq.get(timeout=0.5)
                if song is None:
                    continue
                if song is _SENTINEL_SONG:
                    break
                if not pq.claim(song["id"]):
                    continue
                itunes_result = itunes_lookup(song["artist"], song["title"])
                if itunes_result:
                    album_name, art_url = itunes_result
                else:
                    gdrive_url = gdrive_art_lookup(song["artist"])
                    if gdrive_url:
                        album_name, art_url = "__artist__", gdrive_url
                    else:
                        result_q.put(song["id"])
                        continue
                with write_lock:
                    album_art_id = get_or_create_album_art(conn, song["artist"], album_name, art_url)
                    link_song_album_art(conn, song["id"], album_art_id)
                dest = ART_DIR / f"{album_art_id}.jpg"
                if dest.exists():
                    result_q.put(song["id"])
                else:
                    dl_q.put((song["id"], album_art_id, art_url))

        def download_loop() -> None:
            while not cancel.is_set():
                try:
                    item = dl_q.get(timeout=0.5)
                except queue.Empty:
                    continue
                if item is None:
                    break
                song_id, album_art_id, url = item
                dest = ART_DIR / f"{album_art_id}.jpg"
                if dest.exists():
                    result_q.put(song_id)
                    continue
                try:
                    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200:
                        dest.write_bytes(resp.content)
                        result_q.put(song_id)
                except Exception:
                    pass

        with ThreadPoolExecutor(max_workers=self._n_resolve) as rpool, \
             ThreadPoolExecutor(max_workers=self._n_download) as dpool:

            resolve_futs = [rpool.submit(resolve_loop) for _ in range(self._n_resolve)]
            download_futs = [dpool.submit(download_loop) for _ in range(self._n_download)]

            while not self._cancel.is_set():
                try:
                    song_id = result_q.get(timeout=0.1)
                    completed[0] += 1
                    self.art_ready.emit(song_id)
                    progress_val = min(completed[0] / total, 1.0) if total else 1.0
                    self.progress.emit(progress_val)
                    self.status.emit(f"Fetching art… ({completed[0]}/{total})")
                except queue.Empty:
                    pass

                if not sentinels_sent[0] and all(f.done() for f in resolve_futs):
                    for _ in range(self._n_download):
                        self._dl_q.put(None)
                    sentinels_sent[0] = True

                if sentinels_sent[0] and all(f.done() for f in download_futs):
                    break

        while not result_q.empty():
            song_id = result_q.get_nowait()
            completed[0] += 1
            self.art_ready.emit(song_id)

        self.finished.emit()
```

- [ ] **Step 4: Update imports in `gui/workers.py`**

Update the import block at the top of `gui/workers.py`:

```python
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QThread, Signal, Slot
import requests
import queue
import threading

from db import upsert_songs, ART_DIR, get_or_create_album_art, link_song_album_art
from downloader import download
from installer import install_pairs
from sources.fucuco import fetch_all as fetch_fucuco
from sources.fusersoundlab import fetch_all as fetch_fsl
from sources.art_resolver import bulk_resolve, itunes_lookup
from sources.gdrive_art_index import lookup as gdrive_art_lookup
```

- [ ] **Step 5: Run new ParallelArtWorker tests**

```
pytest tests/test_workers.py::test_parallel_art_worker_resolves_via_itunes_and_downloads tests/test_workers.py::test_parallel_art_worker_falls_back_to_gdrive tests/test_workers.py::test_parallel_art_worker_emits_finished_with_no_pending tests/test_workers.py::test_parallel_art_worker_stop_terminates_gracefully tests/test_workers.py::test_parallel_art_worker_skips_existing_file -v
```

Expected: All pass.

- [ ] **Step 6: Run priority queue tests (unchanged, should still pass)**

```
pytest tests/test_workers.py::test_art_priority_queue_foreground_before_background tests/test_workers.py::test_art_priority_queue_claim_prevents_double_processing tests/test_workers.py::test_art_priority_queue_promote_skips_claimed tests/test_workers.py::test_art_priority_queue_sentinel_terminates_consumer -v
```

Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add gui/workers.py tests/test_workers.py
git commit -m "feat: update ParallelArtWorker to iTunes resolver and album-level storage"
```

---

## Task 4: SingleArtWorker — iTunes Resolver and album_art_id

**Files:**
- Modify: `gui/workers.py`
- Test: `tests/test_workers.py`

- [ ] **Step 1: Write failing tests for updated SingleArtWorker**

Add these tests to `tests/test_workers.py`:

```python
def test_single_art_worker_resolves_via_itunes_and_downloads(tmp_path):
    art_dir = tmp_path / "art"
    import sqlite3
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE album_art (
            id INTEGER PRIMARY KEY, artist TEXT NOT NULL, album TEXT NOT NULL,
            art_url TEXT, UNIQUE(artist, album)
        );
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            album_art_id INTEGER, source TEXT
        );
        INSERT INTO songs VALUES (42, 'Daft Punk', 'Get Lucky', NULL, 'fucuco');
    """)
    song = {"id": 42, "artist": "Daft Punk", "title": "Get Lucky", "album_art_id": None}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"FAKEIMAGE"
    collected = []

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.itunes_lookup", return_value=("RAM", "http://itunes.com/art.jpg")), \
         patch("gui.workers.requests.get", return_value=mock_resp), \
         patch("gui.workers.get_or_create_album_art", return_value=7) as mock_create, \
         patch("gui.workers.link_song_album_art") as mock_link:
        worker = SingleArtWorker(song, conn)
        worker.finished.connect(lambda sid: collected.append(sid))
        worker.run()

    assert (art_dir / "7.jpg").exists()
    assert collected == [42]
    mock_link.assert_called_once_with(conn, 42, 7)


def test_single_art_worker_skips_resolve_when_album_art_id_exists(tmp_path):
    art_dir = tmp_path / "art"
    art_dir.mkdir()
    (art_dir / "5.jpg").write_bytes(b"CACHED")
    conn = MagicMock()
    song = {"id": 7, "artist": "Daft Punk", "title": "Get Lucky", "album_art_id": 5}

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.itunes_lookup") as mock_itunes, \
         patch("gui.workers.requests.get") as mock_get:
        worker = SingleArtWorker(song, conn)
        worker.run()

    mock_itunes.assert_not_called()
    mock_get.assert_not_called()


def test_single_art_worker_emits_error_on_failure(tmp_path):
    art_dir = tmp_path / "art"
    conn = MagicMock()
    song = {"id": 99, "artist": "Daft Punk", "title": "Get Lucky", "album_art_id": None}
    errors = []

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.itunes_lookup", side_effect=Exception("network error")):
        worker = SingleArtWorker(song, conn)
        worker.error.connect(lambda e: errors.append(e))
        worker.run()

    assert errors and "network error" in errors[0]
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_workers.py::test_single_art_worker_resolves_via_itunes_and_downloads tests/test_workers.py::test_single_art_worker_skips_resolve_when_album_art_id_exists -v
```

Expected: FAIL.

- [ ] **Step 3: Replace `SingleArtWorker` in `gui/workers.py`**

Replace the `SingleArtWorker` class (currently lines 366–404):

```python
class SingleArtWorker(QThread):
    finished = Signal(int)
    error = Signal(str)
    status = Signal(str)

    def __init__(self, song: dict, conn, parent=None):
        super().__init__(parent)
        self._song = song
        self._conn = conn

    def run(self):
        try:
            song_id = self._song["id"]
            album_art_id = self._song.get("album_art_id")

            if album_art_id is None:
                self.status.emit("Looking up art… (1/1)")
                itunes_result = itunes_lookup(self._song["artist"], self._song["title"])
                if itunes_result:
                    album_name, art_url = itunes_result
                else:
                    gdrive_url = gdrive_art_lookup(
                        self._song["artist"], status_cb=self.status.emit
                    )
                    if gdrive_url:
                        album_name, art_url = "__artist__", gdrive_url
                    else:
                        self.finished.emit(song_id)
                        return

                album_art_id = get_or_create_album_art(
                    self._conn, self._song["artist"], album_name, art_url
                )
                link_song_album_art(self._conn, song_id, album_art_id)

            dest = ART_DIR / f"{album_art_id}.jpg"
            if not dest.exists():
                self.status.emit("Downloading art…")
                ART_DIR.mkdir(parents=True, exist_ok=True)
                art_url = self._conn.execute(
                    "SELECT art_url FROM album_art WHERE id = ?", (album_art_id,)
                ).fetchone()[0]
                resp = requests.get(
                    art_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}
                )
                if resp.status_code == 200:
                    dest.write_bytes(resp.content)

            self.finished.emit(song_id)
        except Exception as exc:
            self.error.emit(str(exc) or type(exc).__name__)
```

- [ ] **Step 4: Update `ArtResolveWorker` in `gui/workers.py`**

`ArtResolveWorker` calls `bulk_resolve` — the updated `bulk_resolve` already handles the new schema, so `ArtResolveWorker` itself needs no changes. Verify it still compiles by running:

```
pytest tests/test_workers.py::test_art_resolve_worker_emits_finished -v
```

Expected: Pass (it just calls `bulk_resolve` which is now updated).

- [ ] **Step 5: Remove old `ArtFetchWorker` tests that reference `art_url` on songs**

The `ArtFetchWorker` class is kept but its tests reference the old `art_url` field on songs. Update the three `ArtFetchWorker` tests in `tests/test_workers.py` to use `album_art_id` in the test schema:

The three `ArtFetchWorker` tests currently use `{"id": 42, "art_url": "..."}`. `ArtFetchWorker` is not being reworked (it's superseded), so leave its tests in place — they test the class internals which still take `art_url`. No changes needed here.

- [ ] **Step 6: Run all SingleArtWorker and related tests**

```
pytest tests/test_workers.py -k "single_art or art_resolve or art_fetch" -v
```

Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add gui/workers.py tests/test_workers.py
git commit -m "feat: update SingleArtWorker to iTunes resolver and album_art_id"
```

---

## Task 5: StatusBar — start_art_resolve Method

**Files:**
- Modify: `gui/status_bar.py`
- Test: `tests/test_status_bar.py`

- [ ] **Step 1: Write failing test**

Open `tests/test_status_bar.py` and add:

```python
def test_start_art_resolve_shows_progress_bar_and_label(qtbot):
    from gui.status_bar import StatusBar
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.start_art_resolve(47)
    assert not bar._progress.isHidden()
    assert "47" in bar._lbl.text()
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_status_bar.py::test_start_art_resolve_shows_progress_bar_and_label -v
```

Expected: FAIL — `start_art_resolve` not defined.

- [ ] **Step 3: Add `start_art_resolve` to `gui/status_bar.py`**

Add after the `set_done` method (after line 52):

```python
def start_art_resolve(self, total: int) -> None:
    self._lbl.setText(f"Looking up art… (0/{total})")
    self._lbl.setStyleSheet(f"color: {TOKENS['fg_muted']}; background: transparent;")
    self._progress.setValue(0)
    self._progress.show()
```

- [ ] **Step 4: Run test**

```
pytest tests/test_status_bar.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add gui/status_bar.py tests/test_status_bar.py
git commit -m "feat: add start_art_resolve to StatusBar"
```

---

## Task 6: MainWindow — Wire progress Signal and start_art_resolve

**Files:**
- Modify: `gui/main_window.py`
- Test: `tests/test_main_window_layout.py`

- [ ] **Step 1: Check existing main window layout tests pass before touching anything**

```
pytest tests/test_main_window_layout.py -v
```

Expected: All pass (baseline).

- [ ] **Step 2: Update `_start_art_resolve` in `gui/main_window.py`**

Replace the existing `_start_art_resolve` method (lines 270–283):

```python
def _start_art_resolve(self):
    self._set_action_buttons_enabled(False)
    pending = count_pending_art(self.conn)
    self.status_bar.start_art_resolve(pending)
    worker = ParallelArtWorker(self.conn)
    worker.status.connect(self.status_bar.set_message)
    worker.progress.connect(self.status_bar.set_progress)
    worker.art_ready.connect(self._on_art_ready)
    worker.finished.connect(self.status_bar.set_idle)
    worker.finished.connect(lambda: self._set_action_buttons_enabled(True))
    self.song_table.visibleSongsChanged.connect(worker.prioritize)
    worker.finished.connect(
        lambda: self.song_table.visibleSongsChanged.disconnect(worker.prioritize)
    )
    self._art_worker = worker
    worker.start()
    self.song_table.emit_visible_songs()
```

- [ ] **Step 3: Run layout tests to confirm no regressions**

```
pytest tests/test_main_window_layout.py -v
```

Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add gui/main_window.py
git commit -m "feat: wire progress signal and start_art_resolve in MainWindow"
```

---

## Task 7: song_delegate — Use album_art_id for Art File Path

**Files:**
- Modify: `gui/song_delegate.py`
- Test: `tests/test_gui_smoke.py` (smoke test)

- [ ] **Step 1: Check smoke tests pass before touching anything**

```
pytest tests/test_gui_smoke.py -v
```

Expected: All pass (baseline).

- [ ] **Step 2: Update `_art_pixmap` in `gui/song_delegate.py`**

Replace the `_art_pixmap` function (lines 54–106):

```python
def _art_pixmap(song: dict, size: int = ART_SIZE) -> QPixmap:
    """Return a cached pixmap for song: real art from disk, or gradient fallback."""
    song_id = song.get("id", 0)
    album_art_id = song.get("album_art_id")
    key = f"art_{song_id}_{size}"
    pm = QPixmap()
    if QPixmapCache.find(key, pm):
        return pm

    # Check disk cache for downloaded art (keyed by album_art_id)
    art_file = ART_DIR / f"{album_art_id}.jpg" if album_art_id is not None else None
    if art_file and art_file.exists():
        source = QPixmap(str(art_file))
        if not source.isNull():
            scaled = source.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - size) // 2
            y = (scaled.height() - size) // 2
            cropped = scaled.copy(x, y, size, size)

            rounded = QPixmap(size, size)
            rounded.fill(Qt.GlobalColor.transparent)
            p = QPainter(rounded)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            clip = QPainterPath()
            clip.addRoundedRect(0, 0, size, size, ART_RADIUS, ART_RADIUS)
            p.setClipPath(clip)
            p.drawPixmap(0, 0, cropped)
            p.end()
            QPixmapCache.insert(key, rounded)
            return rounded

    # Gradient placeholder (keyed by song_id for variety)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    a, b = _PALETTES[abs(song_id) % len(_PALETTES)]
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor(a))
    g.setColorAt(1, QColor(b))
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, ART_RADIUS, ART_RADIUS)
    p.fillPath(path, QBrush(g))
    p.setPen(QPen(QColor(255, 255, 255, 20), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    p.end()
    QPixmapCache.insert(key, pm)
    return pm
```

- [ ] **Step 3: Update the call site in `SongRowDelegate.paint`**

In the `paint` method, find the art drawing line (currently line 170):

```python
p.drawPixmap(art_x, art_y, _art_pixmap(song.get("id", 0)))
```

Change to:

```python
p.drawPixmap(art_x, art_y, _art_pixmap(song))
```

- [ ] **Step 4: Run smoke tests**

```
pytest tests/test_gui_smoke.py -v
```

Expected: All pass.

- [ ] **Step 5: Run full test suite**

```
pytest tests/ -v
```

Expected: All pass. Fix any failures — do not proceed until clean.

- [ ] **Step 6: Commit**

```bash
git add gui/song_delegate.py
git commit -m "feat: update song_delegate to load art from album_art_id file path"
```

---

## Task 8: Final Integration Verification

**Files:** No code changes — manual verification only.

- [ ] **Step 1: Run the full test suite one final time**

```
pytest tests/ -v
```

Expected: All pass.

- [ ] **Step 2: Verify the app launches without errors**

```
python app.py
```

Confirm:
- App opens without traceback
- Song table populates
- "Fetch Art" button is visible and enabled
- Clicking "Fetch Art" shows the status bar progress bar with "Looking up art… (0/N)"
- Status bar shows "Fetching art… (X/N)" while resolving
- Art images appear in song rows as they resolve
- Songs with no art show the gradient placeholder

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: album art redesign complete — iTunes-first, album-level storage"
```
