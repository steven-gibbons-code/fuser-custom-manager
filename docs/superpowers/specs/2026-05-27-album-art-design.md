# Album Art Display — Design Spec

**Date:** 2026-05-27
**Status:** Approved

## Overview

Add real album art to the song list (48px) and detail panel (160px), replacing the current generated gradient placeholders. Art is resolved from a three-source chain at sync time and cached to disk as `{song_id}.jpg`; the UI displays gradients while art loads and swaps in silently. `QPixmap.load()` detects image format from content, so the `.jpg` extension is used uniformly regardless of source format.

---

## Resolution Chain

Sources are tried in order; the first non-null result wins. Only songs with `art_url IS NULL` are looked up — a resolved URL is never overwritten by a re-sync.

1. **FSL API poster field** — `poster` (fallback: `optional_poster`) already present in the `fusersoundlab.com` playlist JSON. Captured at parse time, no extra HTTP call.
2. **MusicBrainz Cover Art Archive** — free, no API key. Search by artist+title to get an MBID, then fetch from `coverartarchive.org/release/{mbid}/front-250`. Rate-limited to 1 req/sec. Returns `None` on no match or 404.
3. **Google Drive art folder** — public folder `14r8__8RAlxPc278yAe82ukq-aiRpgpC0`, organized alphabetically by artist. Scraped with `requests` using the same gdown-style `AF_initDataCallback` parse used for song downloads. Index cached to `~/.fuser_manager/gdrive_art_index.json`; refreshed once per day. Lookup normalizes artist name, finds the matching subfolder, and returns `https://drive.google.com/uc?id={file_id}&export=download` for the first image file found.
4. **Gradient placeholder** — final fallback; existing behavior, no change.

---

## Data Layer

### DB: new `art_url` column

- Added to `songs` table via `_migrate_add_columns` in `db.py` (existing incremental migration path)
- Type: `TEXT`, nullable
- `upsert_songs` `ON CONFLICT` clause: `art_url = COALESCE(excluded.art_url, art_url)` — re-sync never clears a previously resolved URL

### Disk image cache

- Location: `~/.fuser_manager/art/{song_id}.jpg`
- Written by `ArtFetchWorker`; checked by `_art_pixmap` at display time
- No DB column for cache state — presence of the file is the source of truth

---

## New Modules

### `sources/art_resolver.py`

Pure functions, no Qt dependency. Called during sync after `upsert_songs`.

```
resolve_art_url(song: dict) -> str | None
  FSL songs: art_url already set from parse step — skip
  Fucuco songs:
    1. musicbrainz_lookup(artist, title) -> url | None
    2. gdrive_art_lookup(artist) -> url | None
    3. return None
```

Also exposes `bulk_resolve(conn)` which queries the DB for all songs where `art_url IS NULL`, runs the chain for each, and bulk-updates the DB.

### `sources/gdrive_art_index.py`

- `build_index(folder_id) -> dict` — scrapes the GDrive folder page, parses `AF_initDataCallback` JSON, returns `{artist_name_lower: {folder_id, files: [{id, name}]}}`. The folder may be one level (artist subfolders directly) or two levels (letter → artist); the builder should handle both by checking whether top-level entries are image files or subfolders.
- `get_index() -> dict` — loads from `~/.fuser_manager/gdrive_art_index.json` if fresh (< 24h), otherwise calls `build_index` and saves
- `lookup(artist: str) -> str | None` — normalizes artist name, finds entry, returns `uc?id=` URL for first image file

---

## Background Worker: `ArtFetchWorker`

Lives in `gui/workers.py`, follows the pattern of existing `SyncWorker` / `DownloadWorker`.

- **Input:** list of `{id, art_url}` dicts — songs with `art_url` set but no cached image on disk
- **Per song:** `requests.get(art_url)` → write to `~/.fuser_manager/art/{song_id}.jpg`
- **Signals:**
  - `art_ready = Signal(int)` — emitted per song with `song_id`
  - `finished = Signal()`
- **Triggering:** launched automatically after `SyncWorker.finished`, queues only uncached songs
- **Idempotent:** skips songs whose cache file already exists

---

## UI Changes

### `_art_pixmap` (`gui/song_delegate.py`)

Updated lookup order:
1. `QPixmapCache` hit on key `art_{song_id}_{size}` → return immediately
2. `~/.fuser_manager/art/{song_id}.jpg` exists → load, scale with `SmoothTransformation`, round-clip with existing `QPainterPath`, insert into `QPixmapCache`
3. Generate gradient as before → insert into `QPixmapCache`

### Repaint on `art_ready`

`MainWindow` connects `ArtFetchWorker.art_ready(song_id)` to a slot that:
1. Removes `art_{song_id}_*` entries from `QPixmapCache`
2. Calls `list_view.viewport().update()` to repaint affected rows
3. If detail panel is showing that `song_id`, calls `detail_panel.show(song)` to refresh the 160px thumbnail

**No loading spinner** — gradient serves as the loading state; real art swaps in silently.

---

## Sync Flow (updated)

```
SyncWorker.run()
  fetch_all() for each source
    FSL: parse_playlist_json captures poster → art_url
    Fucuco: no art_url
  upsert_songs(conn, songs)
  bulk_resolve(conn)               # new: queries DB for art_url IS NULL, resolves via MusicBrainz + GDrive
  emit finished

MainWindow.on_sync_finished()
  query songs where art_url IS NOT NULL and no cached file
  start ArtFetchWorker(uncached_songs)

ArtFetchWorker.art_ready(song_id)
  invalidate QPixmapCache entry
  repaint list + detail panel
```

---

## Error Handling

- MusicBrainz: network error or non-200 → log warning, return `None`, continue
- GDrive index scrape failure → log warning, skip GDrive step for this sync
- Image download failure in `ArtFetchWorker` → skip that song silently, it will retry on next sync
- Corrupted cache file → `QPixmap.load()` returns null pixmap; `_art_pixmap` falls back to gradient

---

## Out of Scope

- Manual art override per song
- Displaying art source attribution
- Refreshing art for songs that already have a cached image
