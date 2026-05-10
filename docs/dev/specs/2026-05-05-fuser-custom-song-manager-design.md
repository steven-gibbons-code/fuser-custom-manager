# Fuser Custom Song Manager — Design Spec

**Date:** 2026-05-05

## Goal

A local Python GUI app that lets the user browse, search, and install custom songs for Fuser from the fucuco.online catalog (backed by a public Google Sheet) and fusersoundlab.com, with songs installed as `.pak`/`.sig` pairs under `C:\Fuser\Fuser\Content\Paks\custom_songs\<artist>\`.

---

## Data Sources

### fucuco.online — three Google Sheet tabs

All three tabs are fetched via:
```
https://docs.google.com/spreadsheets/d/1LdMeksBBV8YHo1rfgEWAfegEyRIhcGUjv96RNd10YKk/gviz/tq?tqx=out:csv&sheet=<name>
```

| Tab | `source` value | Notes |
|-----|---------------|-------|
| FULL DATABASE | `fucuco_main` | Primary catalog — artist, title, creator, genre, year, BPM, key, link |
| VGM | `fucuco_vgm` | Same structure + `origin` (source game) |
| NEW SUBMISSIONS | `fucuco_new` | Artist+title may be combined in one column; parse accordingly |

Column B in each tab is the **Complete** field:
- `D` — considered Definitive
- `C` — Complete, with optional notes explaining why not yet Definitive
- blank — not yet complete

### fusersoundlab.com

Scraped via `requests` + `BeautifulSoup4`. Each track yields: title, artist, key, BPM, pack name, Google Drive link.

---

## Normalised Song Schema

All sources normalise to this shape before writing to SQLite:

| Field | Type | Description |
|-------|------|-------------|
| `source` | TEXT | `fucuco_main`, `fucuco_vgm`, `fucuco_new`, `fusersoundlab` |
| `artist` | TEXT | Performing artist |
| `title` | TEXT | Song title |
| `creator` | TEXT | Modder who made the custom |
| `genre` | TEXT | |
| `year` | INTEGER | |
| `bpm` | INTEGER | |
| `key` | TEXT | e.g. `A Minor`, `Gb Major` |
| `de_status` | TEXT | Raw DE STATUS column value |
| `complete` | TEXT | `C`, `D`, or blank |
| `complete_notes` | TEXT | Notes when `complete = 'C'` but not Definitive |
| `stream_opt` | INTEGER | Boolean — stream-optimised flag |
| `origin` | TEXT | VGM only: source game |
| `link` | TEXT | Raw download URL |
| `link_host` | TEXT | `gdrive`, `onedrive`, `mediafire`, `mega`, `other` |
| `last_seen` | TEXT | ISO date of last refresh |

### `is_definitive` (derived, not stored)

Computed at query time:

```
is_definitive =
    (complete == 'D')
    OR (de_status == 'Eligible' AND complete == 'C')
    OR (de_status IS blank AND complete == 'C' AND complete_notes IS blank)
```

---

## Database

Single SQLite file at `~/.fuser_manager/catalog.db`.

```sql
CREATE TABLE songs (
    id             INTEGER PRIMARY KEY,
    source         TEXT,
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
    stream_opt     INTEGER,
    origin         TEXT,
    link           TEXT,
    link_host      TEXT,
    last_seen      TEXT
);

CREATE TABLE installed (
    song_id        INTEGER REFERENCES songs(id),
    pak_path       TEXT,
    sig_path       TEXT,
    installed_at   TEXT
);
```

The `installed` table is populated by scanning `C:\Fuser\Fuser\Content\Paks\custom_songs\` at startup and after each install/uninstall.

---

## Architecture

```
fuser-custom-tool/
    app.py                  # Entry point — launches the customtkinter window
    db.py                   # SQLite setup, read/write helpers, is_definitive query
    installer.py            # Move .pak+.sig to custom_songs/<artist>/, update installed table
    downloader.py           # Route by link_host, run gdown, validate .pak+.sig output
    sources/
        __init__.py
        fucuco.py           # Fetch all three Sheet tabs, normalise rows
        fusersoundlab.py    # Scrape HTML, normalise rows
    gui/
        __init__.py
        main_window.py      # Top-level customtkinter App class
        song_table.py       # Paginated, sortable, filterable CTkTable
        detail_panel.py     # Right-panel metadata + Download/Uninstall buttons
        status_bar.py       # Download progress, queue count, error messages
```

Each module has one clear responsibility and communicates through explicit function calls or callbacks — no shared mutable state between GUI and backend.

---

## Download Handling

The downloader inspects `link_host` and dispatches accordingly:

**Google Drive (file or folder):**
1. Run `gdown` (file) or `gdown --folder` (folder) into `~/.fuser_manager/staging/`.
2. Scan output for `.pak`/`.sig` pairs.
3. A folder download may contain multiple pairs — each is treated as a separate install entry.
4. If `gdown` returns a network/auth error → show **error status** (no fallback).
5. If download succeeds but no `.pak`/`.sig` found → show **manual fallback** with copyable raw link.

**OneDrive / MediaFire / MEGA / other:**
- Show raw link immediately as a **manual download prompt**.
- If link is dead (HTTP error, DNS failure) → show **error status** (no manual fallback).

**Staging cleanup:** staging files are removed after a successful install move.

---

## Installer

1. Sanitise artist name: strip filesystem-illegal characters (`< > : " / \ | ? *`), collapse multiple spaces.
2. Create `C:\Fuser\Fuser\Content\Paks\custom_songs\<artist>\` if it doesn't exist.
3. Move `.pak` and `.sig` into the folder.
4. Write a record to the `installed` table.
5. Uninstall: delete both files, remove the `installed` record, remove the artist folder if now empty.

---

## GUI

Single `customtkinter` window (~1200×800).

**Top bar:** live search (title/artist/creator), dropdowns for Source / Genre / Key / DE Status, Definitive-only toggle, BPM range slider, Refresh button, "Last updated" timestamp.

**Main table (~70% width):** columns — Status badge, Artist, Title, Creator, BPM, Key, Genre, Year, Source, Definitive. Sortable, paginated at 100 rows. Installed rows have a subtle green tint.

**Right detail panel (~30% width):** full metadata for selected song including `complete`, `complete_notes`, `origin`, `de_status`, stream-optimised flag; copyable raw link; Download button; Uninstall button (installed songs only) with install path shown.

**Bottom status bar:** active download filename + % + speed, queue count, error messages.

---

## Tech Stack

| Package | Purpose |
|---------|---------|
| `customtkinter` | Modern-looking tkinter UI |
| `requests` | HTTP fetching (Sheet CSV, fusersoundlab scrape) |
| `beautifulsoup4` | HTML parsing for fusersoundlab |
| `gdown` | Google Drive downloads |
| `sqlite3` | Built-in — catalog + install state |

Python 3.11+. No external API keys required.

---

## Project Location

`C:\Users\sgibb\Documents\ClaudeCode\fuser-custom-tool\`
