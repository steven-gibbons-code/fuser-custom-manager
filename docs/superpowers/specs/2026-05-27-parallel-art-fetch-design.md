# Parallel Art Fetch Design

**Date:** 2026-05-27
**Status:** Approved

## Problem

The current art fetch pipeline is fully sequential: `ArtResolveWorker` resolves one URL at a time (bottlenecked by MusicBrainz's 1 req/sec rate limit), then `ArtFetchWorker` downloads images one at a time. With 10,000+ songs, a full run takes several hours. There is no visible-first prioritization — the user sees no art until the process works its way to whatever rows happen to be visible.

## Goals

- Songs visible in the current scroll window get art first (visual impact immediately).
- Overall throughput increases substantially via parallelism (target: 10–20 images/sec during download phase).
- GDrive remains the primary art source; MusicBrainz is a fallback.
- No DB schema changes.
- `SingleArtWorker` (per-song detail panel) is unchanged.

## Architecture

```
SongTableView (scroll + model-reset events)
        │  visible song IDs → re-prioritize to foreground
        ▼
  ArtPriorityQueue  ←── all pending songs enqueued at worker start (priority=1)
        │
        ├──► ResolvePool (3–5 threads)
        │       GDrive-first lookup → MB fallback
        │       writes art_url to DB (write-lock serialized)
        │       pushes (song_id, url) to DownloadQueue
        │
        └──► DownloadPool (8–10 threads)
                downloads image → ART_DIR/{song_id}.jpg
                emits art_ready(song_id) → UI row repaint
```

A single new `ParallelArtWorker` (`QThread`) owns both `ThreadPoolExecutor` pools and bridges results back to Qt signals. It replaces the `ArtResolveWorker` + `ArtFetchWorker` two-step for the bulk fetch flow.

## Components

### ArtPriorityQueue

- Backed by `queue.PriorityQueue` (stdlib, thread-safe).
- Priority `0` = foreground (visible rows), `1` = background.
- Items: `(priority, song_id, artist, title, art_url_or_none)`.
- Songs already on disk (image file exists) are skipped at dequeue time.

### ParallelArtWorker (QThread)

**Signals:**
- `art_ready(int)` — song_id whose image is now on disk; triggers delegate repaint.
- `status(str)` — progress string for the status bar (e.g., `"Fetching art… 42/10000"`).
- `finished()` — emitted when both pools drain.

**Slots:**
- `prioritize(list[int])` — accepts visible song IDs from `SongTableView`, re-enqueues matching items at priority `0`.
- `stop()` — sets a cancel flag; pools drain gracefully.

**Lifecycle:**
1. On `run()`: load all songs where `art_url IS NULL OR image file missing` from DB, enqueue all at priority `1`.
2. Start resolve pool and download pool.
3. Resolve threads pop from `ArtPriorityQueue`, resolve URL, write to DB, push to internal download queue.
4. Download threads pop from download queue, fetch image, emit `art_ready`.
5. When `ArtPriorityQueue` is empty and all resolve futures are done, signal download pool to drain, then emit `finished`.

### Resolve Pool (3–5 threads)

- GDrive lookup via `gdrive_art_lookup` (index already cached on disk; only cost is first artist-folder fetch per unique artist, also cached).
- MB fallback via `musicbrainz_lookup` only if GDrive returns nothing.
- MB rate limit: existing `_throttle()` replaced with a `threading.Lock`-guarded token bucket enforcing 1 req/sec globally across all resolve threads.
- DB writes serialized via a `threading.Lock` within `ParallelArtWorker`.

### Download Pool (8–10 threads)

- Simple `requests.get` with 15s timeout, same headers as current `ArtFetchWorker`.
- Failed downloads are skipped silently (no retry, consistent with current behavior).
- Emits `art_ready(song_id)` via `QMetaObject.invokeMethod` or a thread-safe signal bridge.

### SongTableView changes

- `verticalScrollBar().valueChanged` connects to `_on_scroll`.
- `_on_scroll` computes visible row range: `first = rowAt(0)`, `last = rowAt(viewport.height() - 1)`, extracts song IDs from model rows in that range.
- Emits `visibleSongsChanged(list[int])` signal.
- Model reset also triggers `_on_scroll` so filter changes re-prioritize immediately.
- `MainWindow` connects `visibleSongsChanged` to `ParallelArtWorker.prioritize` when a worker is running.

### MainWindow changes

- `_start_art_fetch()` replaces the existing `_start_art_resolve` / `_start_art_fetch` two-step.
- Creates `ParallelArtWorker`, connects signals, starts it.
- `ArtResolveWorker` and `ArtFetchWorker` classes are retained (tests + any future single-phase use) but not launched by the bulk flow.

## Data Flow

```
pending songs (DB query)
    → ArtPriorityQueue (priority=1)
        ← scroll events re-prioritize visible subset to priority=0
    → resolve thread: GDrive → (MB fallback) → art_url
        → update_art_url(conn, song_id, url)   [write-locked]
        → DownloadQueue: (song_id, url)
    → download thread: requests.get(url)
        → write ART_DIR/{song_id}.jpg
        → art_ready(song_id) signal
    → SongRowDelegate repaints row
```

## Concurrency & Safety

- `ArtPriorityQueue` and the internal download queue are both `queue.Queue` / `queue.PriorityQueue` — thread-safe by design.
- DB writes from resolve threads go through a single `threading.Lock`; reads (initial query) happen before threads start.
- SQLite connection is opened with `check_same_thread=False` (already the case).
- Cancel flag is a `threading.Event`; threads check it between items.
- Qt signals from worker threads use `Qt.ConnectionType.QueuedConnection` (default for cross-thread signals).

## Testing

- `ParallelArtWorker` unit tests: mock resolve function + mock downloader, verify visible songs (priority=0) are resolved before background songs (priority=1).
- MB token bucket (replacement for `_throttle`) unit tests with a mock clock.
- `SongTableView.visibleSongsChanged` smoke test: verify signal emits correct row IDs on scroll.
- Existing `ArtResolveWorker`, `ArtFetchWorker`, and `SingleArtWorker` tests untouched.

## Out of Scope

- Eager GDrive index pre-build (Option C) — deferred, can be added later as an optional background step.
- Retry logic for failed downloads.
- Per-source concurrency tuning UI.
