# Refresh Mode Dialog & Art Pipeline Sequencing — Design Spec

**Date:** 2026-05-27
**Status:** Approved

## Overview

Split the refresh pipeline so songs become visible immediately after fetch/upsert, without waiting for art URL resolution. Add a pre-refresh dialog (when pending art exists) letting the user choose Songs+Art or Songs only. Add a separate "Fetch Art" toolbar button for art-only runs.

---

## Problem

`RefreshWorker.run()` currently chains fetch → upsert → `bulk_resolve` before emitting `finished`. The table doesn't refresh until all art URL resolution completes (MusicBrainz at 1 req/sec + GDrive scrape), blocking the user from seeing updated song data for several minutes.

---

## Worker Split

### `RefreshWorker` (modified)

Stripped of `bulk_resolve`. Does only:
1. `fetch_fucuco() + fetch_fsl()`
2. `upsert_songs(conn, songs)`
3. `emit finished`

Signals: `finished`, `error`, `status` (unchanged interface).

### `ArtResolveWorker` (new, `gui/workers.py`)

Runs `bulk_resolve(conn, progress_cb=self.status.emit)`.

```python
class ArtResolveWorker(QThread):
    finished = Signal()
    error = Signal(str)
    status = Signal(str)

    def __init__(self, conn, parent=None): ...

    def run(self):
        try:
            bulk_resolve(self._conn, progress_cb=self.status.emit)
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc) or type(exc).__name__)
```

---

## Refresh Mode Dialog

### `RefreshModeDialog` (`gui/refresh_mode_dialog.py`)

A `QDialog` shown before any network work starts, only when `_count_pending_art(conn) > 0`.

**Content:**
```
Art sources need updating

N songs are missing art URLs. Resolving these requires
MusicBrainz lookups (1 req/sec) and may scrape a large
Google Drive index. This can take several minutes.

[ Songs + Art ]    [ Songs only ]
```

- **Songs + Art** → `exec()` returns `True`
- **Songs only** → `exec()` returns `False`
- Closing the dialog (X / Escape) → treated as Songs only (`False`)

### DB helper (new, `db.py`)

```python
def count_pending_art(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM songs WHERE art_url IS NULL AND source != 'fusersoundlab'"
    ).fetchone()[0]
```

---

## Toolbar: Fetch Art Button

A `QPushButton("Fetch Art")` added to the filter bar toolbar, next to the Refresh button.

- Always visible
- Disabled while any art worker (`ArtResolveWorker` or `ArtFetchWorker`) is running
- On click: calls `_start_art_resolve()` directly — no dialog, no song fetch

---

## MainWindow Orchestration

### Refresh flow

```
User clicks Refresh
  → check count_pending_art(conn)
  → if > 0: show RefreshModeDialog → include_art = True/False
  → else: include_art = False
  → disable Refresh + Fetch Art buttons
  → start RefreshWorker
  → on RefreshWorker.finished:
      _refresh_table()          ← songs visible here
      _check_dates_stale()
      if include_art: _start_art_resolve()
      else: re-enable buttons
  → on RefreshWorker.error:
      show error, re-enable buttons
```

### Art resolve flow (shared by both entry points)

```
_start_art_resolve()
  → disable Refresh + Fetch Art buttons
  → start ArtResolveWorker
  → on ArtResolveWorker.finished: _start_art_fetch()
  → on ArtResolveWorker.error: show error, re-enable buttons

_start_art_fetch()
  → (existing ArtFetchWorker logic)
  → on ArtFetchWorker.finished: re-enable buttons + status_bar.set_idle()
```

### Fetch Art button flow

```
User clicks Fetch Art
  → _start_art_resolve()    ← skips song refresh entirely
```

---

## Button State Rules

| State | Refresh | Fetch Art |
|-------|---------|-----------|
| Idle | enabled | enabled |
| RefreshWorker running | disabled | disabled |
| ArtResolveWorker running | disabled | disabled |
| ArtFetchWorker running | disabled | disabled |

---

## Files Changed

| File | Change |
|------|--------|
| `gui/workers.py` | Add `ArtResolveWorker`; remove `bulk_resolve` from `RefreshWorker.run` |
| `gui/refresh_mode_dialog.py` | New: `RefreshModeDialog` |
| `db.py` | Add `count_pending_art(conn)` |
| `gui/main_window.py` | Rewrite `_start_refresh`; add `_start_art_resolve`; add Fetch Art button; update button state management |
| `gui/filter_bar.py` | Expose method to add/enable/disable Fetch Art button (if needed) |

---

## Out of Scope

- Persisting the user's Songs/Art choice across sessions
- A progress bar for art resolution (status bar messages are sufficient)
- Cancelling an in-progress art resolve
