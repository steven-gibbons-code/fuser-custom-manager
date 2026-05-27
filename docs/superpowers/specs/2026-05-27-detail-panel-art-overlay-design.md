# Detail Panel Art Overlay — Design Spec

**Goal:** Show a download glyph over the 160×160 gradient art in the detail panel. Clicking it fetches art for that song only. The glyph is always visible on gradient fallbacks and hidden on resolved art.

---

## Overlay Structure

`_art_overlay_btn` is a `QPushButton` parented directly to `_art_lbl` (the 160×160 art `QLabel`), centered on it at ~44×44px. It displays a `↓` glyph in a semi-transparent rounded style that sits visually over the gradient.

**On click:** the button hides; `_art_spinner_lbl` (a `QLabel`) appears in the same position, cycling through the Unicode braille spinner (`⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏`) driven by a `QTimer` at ~100ms per frame.

**Visibility rules, managed in `show()` and `clear()`:**
- `show(song)`: if `not (ART_DIR / f"{song['id']}.jpg").exists()` → show button, hide spinner. Otherwise hide both.
- `clear()`: hide both, stop timer.

When art arrives, `MainWindow._on_art_ready` already calls `detail_panel.show(song)` — that re-runs the visibility check, swaps to real art, and hides the overlay naturally. No separate hide call needed.

---

## Signal Flow and Worker

`DetailPanel` adds `fetch_art_requested = Signal(dict)`. Button click emits it with `self._song`.

`MainWindow` connects it to a new `_fetch_art_for_song(song)` method. This is a targeted single-song fetch — it does not touch toolbar buttons or the global refresh pipeline.

**New `SingleArtWorker(QThread)` in `gui/workers.py`:**
1. If `song["art_url"]` is `None`: call `musicbrainz_lookup(artist, title)`, fall back to `gdrive_art_lookup(artist)`, save URL to DB via `update_art_url`
2. Download the image to `ART_DIR / f"{song_id}.jpg"` (skip if already exists)
3. Emit `finished(song_id: int)` on success, `error(str)` on failure

`MainWindow._fetch_art_for_song` instantiates `SingleArtWorker`, connects `finished` to `_on_art_ready` (existing handler — invalidates pixmap cache, refreshes table viewport and detail panel).

---

## File Map

| File | Change |
|------|--------|
| `gui/detail_panel.py` | Add `fetch_art_requested` signal; add `_art_overlay_btn`, `_art_spinner_lbl`, `_spinner_timer`; update `show()`, `clear()` |
| `gui/workers.py` | Add `SingleArtWorker` |
| `gui/main_window.py` | Connect `fetch_art_requested` to new `_fetch_art_for_song` |
| `tests/test_detail_panel.py` | New — 4 tests |
| `tests/test_workers.py` | Add 3 tests for `SingleArtWorker` |

---

## Testing

**`tests/test_detail_panel.py` (new):**
- `test_overlay_visible_when_no_art_on_disk` — `show(song)` with no cached file → button visible
- `test_overlay_hidden_when_art_on_disk` — `show(song)` with a real `.jpg` in `ART_DIR` → button hidden
- `test_overlay_hidden_on_clear` — `clear()` → button hidden
- `test_fetch_art_requested_emitted_on_click` — clicking button emits `fetch_art_requested` with the song dict

**`tests/test_workers.py` additions:**
- `test_single_art_worker_resolves_and_downloads` — mocks `musicbrainz_lookup` + `requests.get`, verifies file written and `finished(song_id)` emitted
- `test_single_art_worker_skips_resolve_when_art_url_exists` — song already has `art_url`, verifies `musicbrainz_lookup` not called
- `test_single_art_worker_emits_error_on_failure` — lookup raises, verifies `error` emitted
