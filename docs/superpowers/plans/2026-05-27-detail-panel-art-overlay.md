# Detail Panel Art Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a clickable download glyph over gradient art in the detail panel that fetches art for just that one song.

**Architecture:** `SingleArtWorker` handles the resolve+download for one song. `DetailPanel` grows a `fetch_art_requested` signal and an overlay button (always visible on gradient, hidden on resolved art) with a braille spinner while fetching. `MainWindow` connects the signal to a new `_fetch_art_for_song` method that starts the worker.

**Tech Stack:** PySide6 (QThread, Signal, QTimer, QPushButton, QLabel), pytest + pytest-qt

---

## File Map

| File | Change |
|------|--------|
| `gui/workers.py` | Add `SingleArtWorker`; extend imports |
| `gui/detail_panel.py` | Add `fetch_art_requested` signal; add overlay button + spinner + timer; update `show()`, `clear()` |
| `gui/main_window.py` | Import `SingleArtWorker`; add `_fetch_art_for_song`; connect signal |
| `tests/test_workers.py` | Add 3 tests for `SingleArtWorker` |
| `tests/test_detail_panel.py` | **New** — 4 tests |
| `tests/test_main_window_layout.py` | Add 1 test for `_fetch_art_for_song` wiring |

---

### Task 1: `SingleArtWorker`

**Files:**
- Modify: `gui/workers.py`
- Modify: `tests/test_workers.py`

**Context:** `gui/workers.py` already imports `bulk_resolve` from `sources.art_resolver` and `ART_DIR` from `db`. The new worker uses `musicbrainz_lookup` and `gdrive_art_lookup` individually (not `bulk_resolve`) so it can handle one song. `gdrive_art_index.lookup` accepts `status_cb=None`. `ArtFetchWorker` tests use `worker.run()` directly (synchronous) — do the same here.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_workers.py`:

Update the import line at the top from:
```python
from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker, ArtFetchWorker, ArtResolveWorker
```
to:
```python
from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker, ArtFetchWorker, ArtResolveWorker, SingleArtWorker
```

Then add these three tests after the existing tests:

```python
def test_single_art_worker_resolves_and_downloads(tmp_path):
    art_dir = tmp_path / "art"
    conn = MagicMock()
    song = {"id": 42, "artist": "Daft Punk", "title": "Get Lucky", "art_url": None}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"FAKEIMAGE"
    collected = []

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.musicbrainz_lookup", return_value="http://mb.com/art.jpg"), \
         patch("gui.workers.requests.get", return_value=mock_resp), \
         patch("gui.workers.update_art_url") as mock_update:
        worker = SingleArtWorker(song, conn)
        worker.finished.connect(lambda sid: collected.append(sid))
        worker.run()

    assert (art_dir / "42.jpg").exists()
    assert (art_dir / "42.jpg").read_bytes() == b"FAKEIMAGE"
    assert collected == [42]
    mock_update.assert_called_once_with(conn, 42, "http://mb.com/art.jpg")


def test_single_art_worker_skips_resolve_when_art_url_exists(tmp_path):
    art_dir = tmp_path / "art"
    conn = MagicMock()
    song = {"id": 7, "artist": "Daft Punk", "title": "Get Lucky",
            "art_url": "http://existing.com/art.jpg"}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"FAKEIMAGE"

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.musicbrainz_lookup") as mock_mb, \
         patch("gui.workers.requests.get", return_value=mock_resp):
        worker = SingleArtWorker(song, conn)
        worker.run()

    mock_mb.assert_not_called()
    assert (art_dir / "7.jpg").exists()


def test_single_art_worker_emits_error_on_failure(tmp_path):
    art_dir = tmp_path / "art"
    conn = MagicMock()
    song = {"id": 99, "artist": "Daft Punk", "title": "Get Lucky", "art_url": None}
    errors = []

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.musicbrainz_lookup", side_effect=Exception("network error")):
        worker = SingleArtWorker(song, conn)
        worker.error.connect(lambda e: errors.append(e))
        worker.run()

    assert errors and "network error" in errors[0]
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_workers.py::test_single_art_worker_resolves_and_downloads tests/test_workers.py::test_single_art_worker_skips_resolve_when_art_url_exists tests/test_workers.py::test_single_art_worker_emits_error_on_failure -v
```

Expected: FAIL with `ImportError: cannot import name 'SingleArtWorker'`

- [ ] **Step 3: Implement changes in `gui/workers.py`**

**3a.** Replace the first three import lines:
```python
from db import upsert_songs, ART_DIR
```
with:
```python
from db import upsert_songs, ART_DIR, update_art_url
```

**3b.** Replace:
```python
from sources.art_resolver import bulk_resolve
```
with:
```python
from sources.art_resolver import bulk_resolve, musicbrainz_lookup
from sources.gdrive_art_index import lookup as gdrive_art_lookup
```

**3c.** Add `SingleArtWorker` at the end of `gui/workers.py` (after `ArtResolveWorker`):

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
            art_url = self._song.get("art_url")

            if art_url is None:
                self.status.emit("Looking up art…")
                art_url = musicbrainz_lookup(self._song["artist"], self._song["title"])
                if not art_url:
                    art_url = gdrive_art_lookup(
                        self._song["artist"], status_cb=self.status.emit
                    )
                if art_url:
                    update_art_url(self._conn, song_id, art_url)

            if art_url:
                dest = ART_DIR / f"{song_id}.jpg"
                if not dest.exists():
                    self.status.emit("Downloading art…")
                    ART_DIR.mkdir(parents=True, exist_ok=True)
                    resp = requests.get(
                        art_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}
                    )
                    if resp.status_code == 200:
                        dest.write_bytes(resp.content)

            self.finished.emit(song_id)
        except Exception as exc:
            self.error.emit(str(exc) or type(exc).__name__)
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_workers.py::test_single_art_worker_resolves_and_downloads tests/test_workers.py::test_single_art_worker_skips_resolve_when_art_url_exists tests/test_workers.py::test_single_art_worker_emits_error_on_failure -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Run full suite**

```
pytest --tb=short -q
```

Expected: all previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add gui/workers.py tests/test_workers.py
git commit -m "feat: add SingleArtWorker for per-song art resolve+download"
```

---

### Task 2: `DetailPanel` overlay

**Files:**
- Modify: `gui/detail_panel.py`
- Create: `tests/test_detail_panel.py`

**Context:** `_art_lbl` is a `QLabel` with `setFixedSize(160, 160)`. In Qt, you can parent widgets to a `QLabel` and position them with `setGeometry`. The overlay button is parented to `_art_lbl`, centered at `(58, 58, 44, 44)` (i.e., `(160-44)//2 = 58`). The spinner label occupies the same geometry. Visibility is driven by `_update_art_overlay()`, called from `show()` and `clear()`. `ART_DIR` must be imported at module level in `detail_panel.py` so tests can patch `gui.detail_panel.ART_DIR`.

- [ ] **Step 1: Create `tests/test_detail_panel.py`**

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from gui.detail_panel import DetailPanel

_app = QApplication.instance() or QApplication([])

_SONG = {"id": 42, "pak_path": None}


def test_overlay_visible_when_no_art_on_disk(qtbot, tmp_path):
    art_dir = tmp_path / "art"  # directory doesn't exist — no cached file
    with patch("gui.detail_panel.ART_DIR", art_dir):
        panel = DetailPanel()
        qtbot.addWidget(panel)
        panel.show(_SONG)
    assert panel._art_overlay_btn.isVisible()


def test_overlay_hidden_when_art_on_disk(qtbot, tmp_path):
    art_dir = tmp_path / "art"
    art_dir.mkdir()
    (art_dir / "42.jpg").write_bytes(b"FAKE")
    with patch("gui.detail_panel.ART_DIR", art_dir):
        panel = DetailPanel()
        qtbot.addWidget(panel)
        panel.show(_SONG)
    assert not panel._art_overlay_btn.isVisible()


def test_overlay_hidden_on_clear(qtbot, tmp_path):
    art_dir = tmp_path / "art"
    with patch("gui.detail_panel.ART_DIR", art_dir):
        panel = DetailPanel()
        qtbot.addWidget(panel)
        panel.show(_SONG)
        panel.clear()
    assert not panel._art_overlay_btn.isVisible()


def test_fetch_art_requested_emitted_on_click(qtbot, tmp_path):
    art_dir = tmp_path / "art"
    emitted = []
    with patch("gui.detail_panel.ART_DIR", art_dir):
        panel = DetailPanel()
        qtbot.addWidget(panel)
        panel.fetch_art_requested.connect(lambda s: emitted.append(s))
        panel.show(_SONG)
        qtbot.mouseClick(panel._art_overlay_btn, Qt.MouseButton.LeftButton)
    assert len(emitted) == 1
    assert emitted[0]["id"] == 42
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_detail_panel.py -v
```

Expected: FAIL — `AttributeError: type object 'DetailPanel' has no attribute '_art_overlay_btn'` or `AttributeError: fetch_art_requested`.

- [ ] **Step 3: Update imports in `gui/detail_panel.py`**

Add `QTimer` to the `QtCore` import:
```python
from PySide6.QtCore import Signal, Qt, QTimer
```

Add `ART_DIR` import (after the existing `from gui.song_delegate import _art_pixmap` line):
```python
from db import ART_DIR
```

- [ ] **Step 4: Add `fetch_art_requested` signal to `DetailPanel`**

Add to the class body (after the existing signals):
```python
fetch_art_requested = Signal(dict)
```

- [ ] **Step 5: Add overlay widgets and timer in `_build`, after `self._art_lbl` is created**

The current art block in `_build` is:
```python
self._art_lbl = QLabel()
self._art_lbl.setFixedSize(160, 160)
self._art_lbl.setStyleSheet("border-radius: 14px; background: transparent;")
self._art_lbl.setPixmap(_art_pixmap(0, size=160))
layout.addWidget(self._art_lbl)
```

Replace it with:
```python
self._art_lbl = QLabel()
self._art_lbl.setFixedSize(160, 160)
self._art_lbl.setStyleSheet("border-radius: 14px; background: transparent;")
self._art_lbl.setPixmap(_art_pixmap(0, size=160))
layout.addWidget(self._art_lbl)

self._art_overlay_btn = QPushButton("↓", self._art_lbl)
self._art_overlay_btn.setGeometry(58, 58, 44, 44)
self._art_overlay_btn.setStyleSheet(
    "background: rgba(0,0,0,0.55); color: white; border-radius: 22px; "
    "font-size: 20px; border: none;"
)
self._art_overlay_btn.clicked.connect(self._on_fetch_art_clicked)
self._art_overlay_btn.hide()

self._art_spinner_lbl = QLabel("⠋", self._art_lbl)
self._art_spinner_lbl.setGeometry(58, 58, 44, 44)
self._art_spinner_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
self._art_spinner_lbl.setStyleSheet(
    "background: rgba(0,0,0,0.55); color: white; border-radius: 22px; font-size: 16px;"
)
self._art_spinner_lbl.hide()

self._spinner_frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
self._spinner_idx = 0
self._spinner_timer = QTimer(self)
self._spinner_timer.setInterval(100)
self._spinner_timer.timeout.connect(self._tick_spinner)
```

- [ ] **Step 6: Add helper methods to `DetailPanel`**

Add these three methods before `show`:

```python
def _update_art_overlay(self):
    if not self._song:
        self._art_overlay_btn.hide()
        self._art_spinner_lbl.hide()
        self._spinner_timer.stop()
        return
    has_art = (ART_DIR / f"{self._song['id']}.jpg").exists()
    self._art_overlay_btn.setVisible(not has_art)
    if has_art:
        self._art_spinner_lbl.hide()
        self._spinner_timer.stop()

def _on_fetch_art_clicked(self):
    self._art_overlay_btn.hide()
    self._art_spinner_lbl.show()
    self._spinner_timer.start()
    self.fetch_art_requested.emit(self._song)

def _tick_spinner(self):
    self._spinner_idx = (self._spinner_idx + 1) % len(self._spinner_frames)
    self._art_spinner_lbl.setText(self._spinner_frames[self._spinner_idx])
```

- [ ] **Step 7: Call `_update_art_overlay` from `show` and `clear`**

In `show(self, song: dict)`, add at the end (after `self._sync_buttons()`):
```python
self._update_art_overlay()
```

In `clear(self)`, add at the end (after `self._sync_buttons()`):
```python
self._update_art_overlay()
```

- [ ] **Step 8: Run tests to verify they pass**

```
pytest tests/test_detail_panel.py -v
```

Expected: all 4 PASS.

- [ ] **Step 9: Run full suite**

```
pytest --tb=short -q
```

Expected: all previously passing tests still pass.

- [ ] **Step 10: Commit**

```bash
git add gui/detail_panel.py tests/test_detail_panel.py
git commit -m "feat: add art overlay button and spinner to detail panel"
```

---

### Task 3: MainWindow wiring

**Files:**
- Modify: `gui/main_window.py`
- Modify: `tests/test_main_window_layout.py`

**Context:** `_on_art_ready(song_id)` already handles pixmap cache invalidation, table repaint, and `detail_panel.show(song)` refresh — so it naturally hides the spinner (via `_update_art_overlay`) when art arrives. `_fetch_art_for_song` stores the worker in `self._single_art_worker` to prevent garbage collection.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_main_window_layout.py`:

```python
def test_fetch_art_for_song_starts_single_art_worker(qtbot):
    window = _make_app(qtbot)
    song = {"id": 42, "artist": "Daft Punk", "title": "Get Lucky",
            "art_url": None, "pak_path": None}
    with patch("gui.main_window.SingleArtWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        window._fetch_art_for_song(song)
    MockWorker.assert_called_once_with(song, window.conn)
    mock_instance.start.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_main_window_layout.py::test_fetch_art_for_song_starts_single_art_worker -v
```

Expected: FAIL with `AttributeError: 'FuserApp' object has no attribute '_fetch_art_for_song'`.

- [ ] **Step 3: Update imports in `gui/main_window.py`**

Replace the workers import line:
```python
from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker, ArtFetchWorker, ArtResolveWorker
```
with:
```python
from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker, ArtFetchWorker, ArtResolveWorker, SingleArtWorker
```

- [ ] **Step 4: Add `_single_art_worker` attribute in `__init__`**

In `__init__`, after `self._art_worker = None`, add:
```python
self._single_art_worker = None
```

- [ ] **Step 5: Add `_fetch_art_for_song` method**

Add after `_on_art_ready`:

```python
def _fetch_art_for_song(self, song: dict):
    worker = SingleArtWorker(song, self.conn)
    worker.status.connect(self.status_bar.set_message)
    worker.error.connect(self.status_bar.set_error)
    worker.finished.connect(self._on_art_ready)
    self._single_art_worker = worker
    worker.start()
```

- [ ] **Step 6: Connect `detail_panel.fetch_art_requested` signal**

In `_build_ui` (or wherever `detail_panel` signals are connected — look for `self.detail_panel`), add:
```python
self.detail_panel.fetch_art_requested.connect(self._fetch_art_for_song)
```

- [ ] **Step 7: Run the new test**

```
pytest tests/test_main_window_layout.py::test_fetch_art_for_song_starts_single_art_worker -v
```

Expected: PASS.

- [ ] **Step 8: Run full suite**

```
pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add gui/main_window.py tests/test_main_window_layout.py
git commit -m "feat: wire detail panel fetch-art signal to SingleArtWorker"
```
