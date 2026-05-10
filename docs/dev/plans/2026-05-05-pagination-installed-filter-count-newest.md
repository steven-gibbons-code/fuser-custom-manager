# Pagination, Installed Filter, Result Count, Newest Additions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add prev/next pagination, installed/not-installed filter, result count label, and newest-first sort using submit_date from the fucuco sheet.

**Architecture:** DB layer gains `count_songs` (via extracted `_build_where_params` helper), `submit_date` column, and `installed` filter. Fucuco source fetches submit_date. The main window gains a pagination bar (new Row 2), installed and sort dropdowns in the filter bar, and `_page` counter with reset-on-filter logic.

**Tech Stack:** Python 3.11+, sqlite3, customtkinter, existing project stack.

---

## File Map

```
db.py                  — _build_where_params helper, count_songs, submit_date schema/migration/upsert
sources/fucuco.py      — submit_date in normalise_row
gui/main_window.py     — pagination bar, installed dropdown, sort dropdown, _page counter
tests/test_db.py       — count_songs tests, installed filter tests
tests/test_fucuco.py   — submit_date in normalise_row test
```

---

### Task 1: DB layer — count_songs, submit_date, installed filter

**Files:**
- Modify: `db.py`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Add to the end of `tests/test_db.py`:

```python
from db import count_songs

def test_count_songs_total(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG])
    assert count_songs(conn, {}) == 1

def test_count_songs_search_filter(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG])
    assert count_songs(conn, {"search": "Daft"}) == 1
    assert count_songs(conn, {"search": "Nonexistent"}) == 0

def test_count_songs_installed_filter(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG])
    song = get_songs(conn, {})[0]
    assert count_songs(conn, {"installed": "installed"}) == 0
    assert count_songs(conn, {"installed": "not_installed"}) == 1
    mark_installed(conn, song["id"], r"C:\path\song.pak", r"C:\path\song.sig")
    assert count_songs(conn, {"installed": "installed"}) == 1
    assert count_songs(conn, {"installed": "not_installed"}) == 0

def test_get_songs_installed_filter(tmp_path):
    conn = init_db(tmp_path / "test.db")
    upsert_songs(conn, [SONG])
    song = get_songs(conn, {})[0]
    assert len(get_songs(conn, {"installed": "not_installed"})) == 1
    assert len(get_songs(conn, {"installed": "installed"})) == 0
    mark_installed(conn, song["id"], r"C:\path\song.pak", r"C:\path\song.sig")
    assert len(get_songs(conn, {"installed": "installed"})) == 1
    assert len(get_songs(conn, {"installed": "not_installed"})) == 0

def test_schema_has_submit_date(tmp_path):
    conn = init_db(tmp_path / "test.db")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(songs)").fetchall()}
    assert "submit_date" in cols

def test_upsert_stores_submit_date(tmp_path):
    conn = init_db(tmp_path / "test.db")
    song = {**SONG, "submit_date": "2024/05/01"}
    upsert_songs(conn, [song])
    row = get_songs(conn, {})[0]
    assert row["submit_date"] == "2024/05/01"

def test_get_songs_order_by_submit_date(tmp_path):
    conn = init_db(tmp_path / "test.db")
    older = {**SONG, "submit_date": "2023/01/01"}
    newer = {**SONG, "title": "Newer Song",
             "link": "https://drive.google.com/file/d/newer",
             "submit_date": "2024/06/01"}
    upsert_songs(conn, [older, newer])
    rows = get_songs(conn, {"order_by": "s.submit_date", "descending": True})
    assert rows[0]["title"] == "Newer Song"
```

- [ ] **Step 2: Run to verify they fail**

```powershell
pytest tests\test_db.py -v -k "count_songs or installed_filter or submit_date or order_by_submit"
```

Expected: FAIL — `ImportError: cannot import name 'count_songs' from 'db'`

- [ ] **Step 3: Add submit_date to SCHEMA**

In `db.py`, add `submit_date TEXT,` to the SCHEMA songs table before the UNIQUE constraint:

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

CREATE TABLE IF NOT EXISTS installed (
    id           INTEGER PRIMARY KEY,
    song_id      INTEGER UNIQUE REFERENCES songs(id) ON DELETE CASCADE,
    pak_path     TEXT NOT NULL,
    sig_path     TEXT,
    installed_at TEXT NOT NULL
);
"""
```

- [ ] **Step 4: Add submit_date to _migrate_add_columns**

In `_migrate_add_columns`, extend the `new_cols` list:

```python
    new_cols = [
        ("disc1",         "TEXT"),
        ("disc2",         "TEXT"),
        ("disc3",         "TEXT"),
        ("disc4",         "TEXT"),
        ("download_type", "TEXT"),
        ("quality",       "TEXT"),
        ("submit_date",   "TEXT"),
    ]
```

- [ ] **Step 5: Extract _build_where_params and add installed filter**

After the `_OFFICIAL_LABELS` block, add a new private helper. Then replace the WHERE-building code inside `get_songs` to use it:

```python
def _build_where_params(filters: dict) -> tuple[list[str], list]:
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
    if filters.get("quality"):
        where.append("s.quality = ?")
        params.append(filters["quality"])
    if filters.get("definitive_only"):
        where.append("s.quality IN ('Definitive', 'Official')")
    if filters.get("bpm_min") is not None:
        where.append("s.bpm >= ?")
        params.append(filters["bpm_min"])
    if filters.get("bpm_max") is not None:
        where.append("s.bpm <= ?")
        params.append(filters["bpm_max"])
    if filters.get("installed") == "installed":
        where.append("i.pak_path IS NOT NULL")
    elif filters.get("installed") == "not_installed":
        where.append("i.pak_path IS NULL")
    return where, params
```

Replace the entire WHERE-building block inside `get_songs` (the `where, params = ["1=1"], []` block through the `bpm_max` check) with:

```python
    where, params = _build_where_params(filters)
```

- [ ] **Step 6: Add count_songs function**

Add after `get_songs`:

```python
def count_songs(conn: sqlite3.Connection, filters: dict) -> int:
    where, params = _build_where_params(filters)
    sql = f"""
        SELECT COUNT(*) FROM songs s
        LEFT JOIN installed i ON i.song_id = s.id
        WHERE {' AND '.join(where)}
    """
    return conn.execute(sql, params).fetchone()[0]
```

- [ ] **Step 7: Add submit_date to upsert_songs and _ALLOWED_ORDER**

In `upsert_songs`, add `s.setdefault("submit_date", None)` alongside the other `setdefault` calls, update the INSERT column list, VALUES, and ON CONFLICT UPDATE:

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
            submit_date=excluded.submit_date
    """, enriched)
    conn.commit()
```

In `get_songs`, add `"s.submit_date"` to `_ALLOWED_ORDER`:

```python
    _ALLOWED_ORDER = {
        "s.artist", "s.title", "s.creator", "s.bpm", "s.year",
        "s.genre", "s.key", "s.source", "s.de_status", "s.quality",
        "s.submit_date",
    }
```

- [ ] **Step 8: Run all db tests**

```powershell
pytest tests\test_db.py -v
```

Expected: All tests PASS.

- [ ] **Step 9: Commit**

```powershell
git add db.py tests\test_db.py
git commit -m "feat: count_songs, submit_date, installed filter, _build_where_params refactor"
```

---

### Task 2: submit_date in fucuco normalise_row

**Files:**
- Modify: `sources/fucuco.py`
- Modify: `tests/test_fucuco.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_fucuco.py`:

```python
def test_normalise_includes_submit_date():
    row = {
        "Artist": "Daft Punk", "Title": "Get Lucky", "Creator": "DJTest",
        "Submit Date": "2023/05/01",
        "Link": "https://drive.google.com/file/d/abc",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["submit_date"] == "2023/05/01"

def test_normalise_submit_date_blank_is_none():
    row = {
        "Artist": "A", "Title": "B",
        "Link": "https://drive.google.com/file/d/abc",
    }
    r = normalise_row(row, "fucuco_main")
    assert r["submit_date"] is None
```

- [ ] **Step 2: Run to verify they fail**

```powershell
pytest tests\test_fucuco.py -v -k "submit_date"
```

Expected: FAIL — `KeyError: 'submit_date'`

- [ ] **Step 3: Add submit_date to normalise_row**

In `sources/fucuco.py`, inside `normalise_row`, add after `download_col = _find(h, "Download")`:

```python
    submit_date_col = _find(h, "Submit Date")
```

Add to the return dict after `"download_type"`:

```python
        "download_type":  row.get(download_col or "", "").strip() or None,
        "submit_date":    row.get(submit_date_col or "", "").strip() or None,
        "link":           link,
```

- [ ] **Step 4: Run all fucuco tests**

```powershell
pytest tests\test_fucuco.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add sources\fucuco.py tests\test_fucuco.py
git commit -m "feat: submit_date field in fucuco normalise_row"
```

---

### Task 3: Pagination bar, installed dropdown, sort dropdown in main_window.py

**Files:**
- Modify: `gui/main_window.py`

- [ ] **Step 1: Update import in main_window.py**

Change the `db` import line:

```python
from db import init_db, get_songs, upsert_songs, get_song_by_id, count_songs
```

- [ ] **Step 2: Add _page counter to __init__**

In `FuserApp.__init__`, add `self._page: int = 0` after `self.conn = init_db()`:

```python
    def __init__(self):
        super().__init__()
        self.title("Fuser Custom Song Manager")
        self.geometry("1200x800")
        self.conn: sqlite3.Connection = init_db()
        self._page: int = 0
        scan_and_sync(INSTALL_DIR, self.conn)
        self._build_ui()
        self._refresh_table()
```

- [ ] **Step 3: Replace _build_ui with updated layout**

Replace the entire `_build_ui` method:

```python
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=7)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(3, weight=1)  # table row is now 3

        # Row 0 — search + actions
        top = ctk.CTkFrame(self, height=48)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=(8, 0))
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="Search:").grid(row=0, column=0, padx=6)
        self._search = ctk.StringVar()
        self._search.trace_add("write", lambda *_: self._filter_changed())
        ctk.CTkEntry(top, textvariable=self._search, width=240).grid(
            row=0, column=1, padx=4, sticky="ew")

        self._refresh_btn = ctk.CTkButton(top, text="Refresh Sources", width=130,
                                           command=self._start_refresh)
        self._refresh_btn.grid(row=0, column=3, padx=6)

        self._updated_lbl = ctk.CTkLabel(top, text="", text_color="#aaaaaa")
        self._updated_lbl.grid(row=0, column=4, padx=6)

        # Row 1 — filter bar
        fbar = ctk.CTkFrame(self, height=40)
        fbar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 0))

        SOURCES = ["All Sources", "fucuco_main", "fucuco_vgm", "fusersoundlab"]
        ctk.CTkLabel(fbar, text="Source:").pack(side="left", padx=6)
        self._source = ctk.StringVar(value="All Sources")
        ctk.CTkOptionMenu(fbar, variable=self._source, values=SOURCES, width=130,
                           command=lambda _: self._filter_changed()).pack(side="left", padx=4)

        QUALITIES = ["All Quality", "Official", "Definitive", "Complete", "Other"]
        ctk.CTkLabel(fbar, text="Quality:").pack(side="left", padx=(10, 4))
        self._quality = ctk.StringVar(value="All Quality")
        ctk.CTkOptionMenu(fbar, variable=self._quality, values=QUALITIES, width=110,
                           command=lambda _: self._filter_changed()).pack(side="left", padx=4)

        INSTALLED_OPTS = ["All", "Installed", "Not installed"]
        ctk.CTkLabel(fbar, text="Status:").pack(side="left", padx=(10, 4))
        self._installed = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(fbar, variable=self._installed, values=INSTALLED_OPTS, width=110,
                           command=lambda _: self._filter_changed()).pack(side="left", padx=4)

        ctk.CTkLabel(fbar, text="Genre:").pack(side="left", padx=(10, 4))
        self._genre = ctk.StringVar()
        self._genre.trace_add("write", lambda *_: self._filter_changed())
        ctk.CTkEntry(fbar, textvariable=self._genre, width=100).pack(side="left", padx=2)

        ctk.CTkLabel(fbar, text="BPM:").pack(side="left", padx=(10, 4))
        self._bpm_min = ctk.StringVar()
        self._bpm_max = ctk.StringVar()
        self._bpm_min.trace_add("write", lambda *_: self._filter_changed())
        self._bpm_max.trace_add("write", lambda *_: self._filter_changed())
        ctk.CTkEntry(fbar, textvariable=self._bpm_min, width=55,
                      placeholder_text="min").pack(side="left", padx=2)
        ctk.CTkLabel(fbar, text="–").pack(side="left")
        ctk.CTkEntry(fbar, textvariable=self._bpm_max, width=55,
                      placeholder_text="max").pack(side="left", padx=2)

        SORT_OPTS = ["Artist A–Z", "Newest First", "BPM ↑", "BPM ↓"]
        ctk.CTkLabel(fbar, text="Sort:").pack(side="left", padx=(10, 4))
        self._sort = ctk.StringVar(value="Artist A–Z")
        ctk.CTkOptionMenu(fbar, variable=self._sort, values=SORT_OPTS, width=120,
                           command=lambda _: self._filter_changed()).pack(side="left", padx=4)

        # Row 2 — pagination bar
        pbar = ctk.CTkFrame(self, height=36)
        pbar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 0))

        self._prev_btn = ctk.CTkButton(pbar, text="← Prev", width=70,
                                        command=self._prev_page, state="disabled")
        self._prev_btn.pack(side="left", padx=6)

        self._page_lbl = ctk.CTkLabel(pbar, text="Page 1 of 1  (0 songs)")
        self._page_lbl.pack(side="left", padx=8)

        self._next_btn = ctk.CTkButton(pbar, text="Next →", width=70,
                                        command=self._next_page, state="disabled")
        self._next_btn.pack(side="left", padx=6)

        # Row 3 — table + detail
        self.song_table = SongTable(self, on_select=self._on_select)
        self.song_table.grid(row=3, column=0, sticky="nsew", padx=(8, 4), pady=8)

        self.detail_panel = DetailPanel(self, conn=self.conn,
                                         on_download=self._on_download,
                                         on_uninstall=self._on_uninstall)
        self.detail_panel.grid(row=3, column=1, sticky="nsew", padx=(4, 8), pady=8)

        # Row 4 — status bar
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=4, column=0, columnspan=2,
                              sticky="ew", padx=8, pady=(0, 8))
```

- [ ] **Step 4: Replace _filters and _refresh_table, add helpers**

Replace the `# ── Helpers` section:

```python
    # ── Helpers ───────────────────────────────────────────────────────────
    _SORT_MAP = {
        "Artist A–Z":   ("s.artist",      False),
        "Newest First": ("s.submit_date", True),
        "BPM ↑":        ("s.bpm",         False),
        "BPM ↓":        ("s.bpm",         True),
    }
    _INSTALLED_MAP = {
        "Installed":     "installed",
        "Not installed": "not_installed",
    }

    def _filters(self) -> dict:
        f: dict = {
            "search": self._search.get(),
            "offset": self._page * 100,
        }
        if self._source.get() != "All Sources":
            f["source"] = self._source.get()
        if self._quality.get() != "All Quality":
            f["quality"] = self._quality.get()
        installed_val = self._INSTALLED_MAP.get(self._installed.get())
        if installed_val:
            f["installed"] = installed_val
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
        order_by, descending = self._SORT_MAP.get(self._sort.get(), ("s.artist", False))
        f["order_by"] = order_by
        if descending:
            f["descending"] = True
        return f

    def _refresh_table(self):
        filters = self._filters()
        rows = get_songs(self.conn, filters)
        total = count_songs(self.conn, filters)
        self.song_table.load(rows)
        total_pages = max(1, (total + 99) // 100)
        self._page_lbl.configure(
            text=f"Page {self._page + 1} of {total_pages}  ({total:,} songs)")
        self._prev_btn.configure(state="normal" if self._page > 0 else "disabled")
        self._next_btn.configure(
            state="normal" if (self._page + 1) * 100 < total else "disabled")

    def _filter_changed(self):
        self._page = 0
        self._refresh_table()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._refresh_table()

    def _next_page(self):
        self._page += 1
        self._refresh_table()

    def _on_select(self, song: dict):
        self.detail_panel.show(song)
```

- [ ] **Step 5: Run smoke test**

```powershell
pytest tests\test_gui_smoke.py -v
```

Expected: PASS.

- [ ] **Step 6: Run full test suite**

```powershell
pytest tests\ -v
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add gui\main_window.py
git commit -m "feat: pagination bar, installed filter, sort dropdown, result count"
```
