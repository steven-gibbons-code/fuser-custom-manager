# Album Art Redesign: iTunes-First, Album-Level Storage

**Date:** 2026-05-28

## Problem

The current art system stores one `.jpg` file per song ID (`~/.fuser_manager/art/{song_id}.jpg`), causing many redundant downloads when multiple songs share the same album. The primary resolver (GDrive) returns an arbitrary artist-level image rather than accurate album art. MusicBrainz is the only album-aware source but is rate-limited to 1 req/sec and often returns the wrong release.

## Goals

- Accurate album art via iTunes Search API (artist + title → album name + art URL)
- Deduplicate file storage at the album level — one `.jpg` per unique album
- Songs on the same album share one downloaded file; no redundant downloads
- GDrive fallback for songs iTunes cannot resolve
- Placeholder displayed for songs with no resolved art
- Status bar shows X/Y progress with a progress bar fill during resolution
- Clean break from old system: drop `art_url` column, delete old art files, re-resolve everything

## Non-Goals

- Per-song unique art (different songs on the same album show the same cover — by design)
- Offline/local art scanning
- User-supplied custom art

---

## Database Schema

### New table: `album_art`

```sql
CREATE TABLE album_art (
    id      INTEGER PRIMARY KEY,
    artist  TEXT NOT NULL,
    album   TEXT NOT NULL,
    art_url TEXT,
    UNIQUE(artist, album)
);
```

`artist` and `album` are the normalized strings returned by iTunes (or the sentinel `"__artist__"` for GDrive-resolved entries). `art_url` is the source URL used to download the image.

### Songs table changes

- **Add:** `album_art_id INTEGER REFERENCES album_art(id)` — replaces `art_url`
- **Drop:** `art_url TEXT` — zeroed out or dropped depending on SQLite version

### Art file naming

Art files move from `{song_id}.jpg` to `{album_art_id}.jpg`. All songs on the same album point to one file.

### Migration (clean break, runs in `init_db`)

1. Create `album_art` table if not exists
2. Add `album_art_id` column to `songs` if not exists
3. Zero out or drop `art_url` column from `songs`
4. Delete all existing files in `~/.fuser_manager/art/`

---

## Resolver Pipeline

### iTunes lookup — primary

Function: `itunes_lookup(artist: str, title: str) -> tuple[str, str] | None`

- Endpoint: `https://itunes.apple.com/search?term={artist}+{title}&entity=song&limit=5`
- Returns `(album_name, artwork_url)` from the best-matching result, or `None`
- Artwork URL returned by iTunes is high-resolution; resize or use as-is
- Throttled to ~3 req/sec (well under the ~20/min community limit)
- Replaces `musicbrainz_lookup` entirely — MusicBrainz is removed

### GDrive fallback — secondary

- Existing `gdrive_art_lookup(artist)` unchanged
- On a GDrive hit, stored in `album_art` with `album = "__artist__"` as a sentinel
- Keyed as `(artist, "__artist__")` so all GDrive-resolved songs for an artist share one row/file

### Placeholder — tertiary

- Songs with `album_art_id IS NULL` show a bundled placeholder image at display time
- No separate download step — placeholder is a static asset in `assets/`

### Deduplication logic (runs per song before any download)

```
# Step 1: resolve to (album_name, art_url)
itunes_result = itunes_lookup(artist, title)   # returns (album_name, art_url) | None
if itunes_result:
    album_name, art_url = itunes_result
else:
    gdrive_url = gdrive_art_lookup(artist)     # returns url | None
    if gdrive_url:
        album_name, art_url = "__artist__", gdrive_url
    else:
        leave album_art_id NULL (placeholder shown)
        return

# Step 2: deduplicate against album_art table
look up (artist, album_name) in album_art table
  → row exists AND {id}.jpg on disk  → set songs.album_art_id = id, done
  → row exists AND file missing      → re-download to {id}.jpg, set songs.album_art_id, done
  → row not exists                   → INSERT into album_art, download {id}.jpg, set songs.album_art_id
```

---

## Worker Updates

### `ParallelArtWorker`

- DB query changes from `WHERE art_url IS NULL` to `WHERE album_art_id IS NULL AND source != 'fusersoundlab'`
- Add `progress = Signal(float)` signal (0.0–1.0) for progress bar
- Total pending count is known at start of `run()` — used for X/Y display
- `resolve_loop` calls `itunes_lookup` → `gdrive_art_lookup` → gives up
- On a hit: insert/find `album_art` row, download if needed, update `songs.album_art_id`
- Status messages:
  - During resolve: `"Looking up art… (3/47)"`
  - During download: `"Downloading art… (8/47)"`
- `art_ready` signal still emits `song_id` — display layer unchanged

### `SingleArtWorker`

- Same resolver swap (iTunes → GDrive → give up)
- Status: `"Looking up art… (1/1)"` then `"Downloading art…"`
- Updates `songs.album_art_id` instead of `art_url`

### `ArtResolveWorker` / `ArtFetchWorker`

- Both are effectively superseded by `ParallelArtWorker` in the new flow
- Kept for now but their internal calls updated to use new resolver and schema; can be removed in a follow-up cleanup

---

## Display Updates

### `song_delegate.py`

- Art file path changes from `ART_DIR / f"{song['id']}.jpg"` to `ART_DIR / f"{song['album_art_id']}.jpg"`
- When `album_art_id` is `None`, load the bundled placeholder image from `assets/`

---

## Status Bar Updates

### `StatusBar` additions

- `start_art_resolve(total: int)` — shows progress bar, sets initial label, stores total for reference
- Reuses existing `set_progress(float)` for bar fill
- `set_idle()` called on `finished` to hide bar and reset label

### `MainWindow` wiring

- `worker.progress` → `status_bar.set_progress()`
- `worker.status` → `status_bar.set_message()` (already connected)
- `worker.finished` → `status_bar.set_idle()`
- Before starting the worker, call `count_pending_art(conn)` (already in `db.py`) to get the total, then call `status_bar.start_art_resolve(total)` — this keeps total calculation on the main thread and avoids a cross-thread signal for initialization

---

## File Layout Summary

| What | Old path | New path |
|---|---|---|
| Art files | `~/.fuser_manager/art/{song_id}.jpg` | `~/.fuser_manager/art/{album_art_id}.jpg` |
| Art URL storage | `songs.art_url` | `album_art.art_url` |
| Song → art link | `songs.art_url` (URL string) | `songs.album_art_id` (FK) |
| Resolver source | MusicBrainz → GDrive | iTunes → GDrive |

---

## Open Questions

None — all design decisions resolved.
