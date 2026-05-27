# Refresh Mode Dialog & Art Pipeline Sequencing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the refresh pipeline so songs appear immediately after fetch/upsert, add a pre-refresh dialog when pending art exists (Songs+Art vs Songs only), and add a standalone "Fetch Art" toolbar button.

**Architecture:** `RefreshWorker` drops `bulk_resolve`; a new `ArtResolveWorker` takes it over. `MainWindow._start_refresh` checks for pending art before starting and shows `RefreshModeDialog` if needed. `_start_art_resolve` is a new shared entry point called by both the dialog path and the Fetch Art button.

**Tech Stack:** PySide6 (QDialog, QThread, Signal), SQLite via sqlite3, pytest + pytest-qt

---

## File Map

| File | Change |
|------|--------|
| `db.py` | Add `count_pending_art(conn)` helper |
| `gui/workers.py` | Add `ArtResolveWorker`; remove `bulk_resolve` call from `RefreshWorker.run` |
| `gui/refresh_mode_dialog.py` | **New** — `RefreshModeDialog` |
| `gui/main_window.py` | Update imports; rewrite `_start_refresh`; add `_start_art_resolve`, `_set_action_buttons_enabled`; add Fetch Art button; update `_on_refresh_done`, `_start_art_fetch` |
| `tests/test_db.py` | Add 2 tests for `count_pending_art` |
| `tests/test_workers.py` | Add 3 tests for `ArtResolveWorker`; update `test_refresh_worker_emits_finished` |
| `tests/test_refresh_mode_dialog.py` | **New** — 3 tests |
| `tests/test_main_window_layout.py` | Add 3 tests for new wiring |

---

### Task 1: DB helper — `count_pending_art`

**Files:**
- Modify: `db.py` (after line 302, after `update_art_url`)
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_db.py` (after the last test):

```python
def test_count_pending_art_excludes_fsl_and_resolved(conn):
    from db import count_pending_art
    upsert_songs(conn, [
        {**SONG, "source": "fucuco_main", "art_url": None,                          "title": "Pending"},
        {**SONG, "source": "fucuco_main", "art_url": "http://example.com/a.jpg",    "title": "Resolved"},
        {**SONG, "source": "fusersoundlab", "art_url": None,                        "title": "FSL"},
    ])
    assert count_pending_art(conn) == 1  # only "Pending": fucuco + null art_url


def test_count_pending_art_returns_zero_when_all_resolved(conn):
    from db import count_pending_art
    upsert_songs(conn, [{**SONG, "art_url": "http://example.com/art.jpg", "title": "Done"}])
    assert count_pending_art(conn) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_db.py::test_count_pending_art_excludes_fsl_and_resolved tests/test_db.py::test_count_pending_art_returns_zero_when_all_resolved -v
```

Expected: FAIL with `ImportError: cannot import name 'count_pending_art'`

- [ ] **Step 3: Implement `count_pending_art` in `db.py`**

Add after `update_art_url` (currently the last function in `db.py`, after line 302):

```python
def count_pending_art(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM songs WHERE art_url IS NULL AND source != 'fusersoundlab'"
    ).fetchone()[0]
```

Also add `count_pending_art` to the existing import line in `tests/test_db.py`:

```python
from db import (init_db, upsert_songs, get_songs, mark_installed,
                mark_uninstalled, get_installed, get_setting, set_setting,
                get_songs_with_art_url, update_art_url, ART_DIR, count_pending_art)
```

Then remove the `from db import count_pending_art` lines from inside the two new test functions (now that it's imported at top level).

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_db.py::test_count_pending_art_excludes_fsl_and_resolved tests/test_db.py::test_count_pending_art_returns_zero_when_all_resolved -v
```

Expected: PASS

- [ ] **Step 5: Run full suite**

```
pytest --tb=short -q
```

Expected: all previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add count_pending_art DB helper"
```

---

### Task 2: `ArtResolveWorker` + strip `RefreshWorker`

**Files:**
- Modify: `gui/workers.py`
- Modify: `tests/test_workers.py`

**Context:** `gui/workers.py` currently has `RefreshWorker.run` calling `bulk_resolve` (line 27). This blocks the `finished` signal — and therefore the table refresh — until all art URL resolution completes. Remove that call. Add `ArtResolveWorker` which does only `bulk_resolve`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_workers.py` (after existing tests):

```python
def test_art_resolve_worker_emits_finished(qtbot):
    conn = MagicMock()
    worker = ArtResolveWorker(conn)
    with patch("gui.workers.bulk_resolve"):
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()


def test_art_resolve_worker_emits_error_on_exception(qtbot):
    conn = MagicMock()
    worker = ArtResolveWorker(conn)
    with patch("gui.workers.bulk_resolve", side_effect=RuntimeError("resolve error")):
        with qtbot.waitSignal(worker.error, timeout=3000) as blocker:
            worker.start()
    assert "resolve error" in blocker.args[0]


def test_art_resolve_worker_calls_bulk_resolve_with_progress_cb(qtbot):
    conn = MagicMock()
    worker = ArtResolveWorker(conn)
    with patch("gui.workers.bulk_resolve") as mock_resolve:
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()
    _, kwargs = mock_resolve.call_args
    assert callable(kwargs.get("progress_cb"))
```

Also update `test_refresh_worker_emits_finished` to assert `bulk_resolve` is NOT called from `RefreshWorker`:

```python
def test_refresh_worker_emits_finished(qtbot, tmp_path):
    conn = MagicMock()
    worker = RefreshWorker(conn)
    mock_songs = [{"title": "A"}, {"title": "B"}]
    with patch("gui.workers.fetch_fucuco", return_value=[mock_songs[0]]), \
         patch("gui.workers.fetch_fsl", return_value=[mock_songs[1]]), \
         patch("gui.workers.upsert_songs") as mock_upsert, \
         patch("gui.workers.bulk_resolve") as mock_resolve:
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()
        mock_upsert.assert_called_once()
        mock_resolve.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_workers.py::test_art_resolve_worker_emits_finished tests/test_workers.py::test_art_resolve_worker_emits_error_on_exception tests/test_workers.py::test_art_resolve_worker_calls_bulk_resolve_with_progress_cb -v
```

Expected: FAIL with `ImportError: cannot import name 'ArtResolveWorker'`

- [ ] **Step 3: Implement changes in `gui/workers.py`**

**3a.** Add `ArtResolveWorker` to the import line at the top of the file — it's used in this module, not imported yet. No change needed for imports since `bulk_resolve` is already imported.

**3b.** Replace `RefreshWorker.run` — remove the `bulk_resolve` call:

```python
class RefreshWorker(QThread):
    finished = Signal()
    error = Signal(str)
    status = Signal(str)

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn

    def run(self):
        try:
            self.status.emit("Refreshing sources…")
            songs = fetch_fucuco() + fetch_fsl()
            upsert_songs(self._conn, songs)
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc) or type(exc).__name__)
```

**3c.** Add `ArtResolveWorker` at the end of `gui/workers.py` (after the existing `ArtFetchWorker` class):

```python
class ArtResolveWorker(QThread):
    finished = Signal()
    error = Signal(str)
    status = Signal(str)

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn

    def run(self):
        try:
            bulk_resolve(self._conn, progress_cb=self.status.emit)
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc) or type(exc).__name__)
```

**3d.** Update the import line in `tests/test_workers.py`:

```python
from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker, ArtFetchWorker, ArtResolveWorker
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_workers.py -v
```

Expected: all pass.

- [ ] **Step 5: Run full suite**

```
pytest --tb=short -q
```

Expected: all previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add gui/workers.py tests/test_workers.py
git commit -m "feat: add ArtResolveWorker, strip bulk_resolve from RefreshWorker"
```

---

### Task 3: `RefreshModeDialog`

**Files:**
- Create: `gui/refresh_mode_dialog.py`
- Create: `tests/test_refresh_mode_dialog.py`

**Context:** This dialog appears before the refresh when `count_pending_art > 0`. "Songs + Art" calls `self.accept()` (returns `QDialog.DialogCode.Accepted`). "Songs only" calls `self.reject()`. Closing the window also rejects. Follows the same import pattern as `gui/batch_results_dialog.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_refresh_mode_dialog.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton
from PySide6.QtCore import Qt
from gui.refresh_mode_dialog import RefreshModeDialog

_app = QApplication.instance() or QApplication([])


def test_dialog_shows_pending_count_in_message(qtbot):
    dlg = RefreshModeDialog(pending_count=42)
    qtbot.addWidget(dlg)
    labels = dlg.findChildren(QLabel)
    assert any("42" in lbl.text() for lbl in labels)


def test_songs_art_button_accepts_dialog(qtbot):
    dlg = RefreshModeDialog(pending_count=5)
    qtbot.addWidget(dlg)
    buttons = dlg.findChildren(QPushButton)
    btn = next(b for b in buttons if b.text() == "Songs + Art")
    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
    assert dlg.result() == QDialog.DialogCode.Accepted


def test_songs_only_button_rejects_dialog(qtbot):
    dlg = RefreshModeDialog(pending_count=5)
    qtbot.addWidget(dlg)
    buttons = dlg.findChildren(QPushButton)
    btn = next(b for b in buttons if b.text() == "Songs only")
    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
    assert dlg.result() == QDialog.DialogCode.Rejected
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_refresh_mode_dialog.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'gui.refresh_mode_dialog'`

- [ ] **Step 3: Create `gui/refresh_mode_dialog.py`**

```python
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton


class RefreshModeDialog(QDialog):
    def __init__(self, pending_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Art sources need updating")
        self.setModal(True)
        self._build(pending_count)

    def _build(self, pending_count: int):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        msg = QLabel(
            f"{pending_count} songs are missing art URLs. Resolving these requires\n"
            "MusicBrainz lookups (1 req/sec) and may scrape a large\n"
            "Google Drive index. This can take several minutes."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)

        songs_art_btn = QPushButton("Songs + Art")
        songs_art_btn.setObjectName("primaryBtn")
        songs_art_btn.clicked.connect(self.accept)
        buttons.addWidget(songs_art_btn)

        songs_only_btn = QPushButton("Songs only")
        songs_only_btn.clicked.connect(self.reject)
        buttons.addWidget(songs_only_btn)

        layout.addLayout(buttons)
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_refresh_mode_dialog.py -v
```

Expected: all 3 pass.

- [ ] **Step 5: Run full suite**

```
pytest --tb=short -q
```

Expected: all previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add gui/refresh_mode_dialog.py tests/test_refresh_mode_dialog.py
git commit -m "feat: add RefreshModeDialog (Songs+Art vs Songs only)"
```

---

### Task 4: MainWindow wiring

**Files:**
- Modify: `gui/main_window.py`
- Modify: `tests/test_main_window_layout.py`

**Context:** This task rewires `_start_refresh`, adds `_start_art_resolve`, `_set_action_buttons_enabled`, the Fetch Art button, and updates `_on_refresh_done` and `_start_art_fetch`. The existing `_on_art_ready` is unchanged.

**Current state of `_start_refresh` (lines 234–243) and `_on_refresh_done` (lines 245–249) and `_start_art_fetch` (lines 251–261) in `gui/main_window.py`:**

```python
# current _start_refresh (lines 234-243)
def _start_refresh(self):
    self.filter_bar.set_refresh_enabled(False)
    worker = RefreshWorker(self.conn)
    worker.status.connect(self.status_bar.set_message)
    worker.finished.connect(self._on_refresh_done)
    worker.error.connect(self.status_bar.set_error)
    worker.finished.connect(lambda: self.filter_bar.set_refresh_enabled(True))
    worker.error.connect(lambda _: self.filter_bar.set_refresh_enabled(True))
    self._active_worker = worker
    worker.start()

# current _on_refresh_done (lines 245-249)
def _on_refresh_done(self):
    self.filter_bar.set_updated_label(f"Updated {date.today().isoformat()}")
    self._refresh_table()
    self._check_dates_stale()
    self._start_art_fetch()

# current _start_art_fetch (lines 251-261)
def _start_art_fetch(self):
    songs = get_songs_with_art_url(self.conn)
    uncached = [s for s in songs if not (ART_DIR / f"{s['id']}.jpg").exists()]
    if not uncached:
        return
    worker = ArtFetchWorker(uncached)
    worker.status.connect(self.status_bar.set_message)
    worker.art_ready.connect(self._on_art_ready)
    worker.finished.connect(self.status_bar.set_idle)
    self._art_worker = worker
    worker.start()
```

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_main_window_layout.py` (after existing tests):

```python
def test_fetch_art_button_exists_in_toolbar(qtbot):
    window = _make_app(qtbot)
    assert hasattr(window, "_fetch_art_btn")
    assert window._fetch_art_btn.text() == "⬇ Fetch Art"


def test_on_refresh_done_re_enables_buttons_when_no_art(qtbot):
    window = _make_app(qtbot)
    with patch.object(window, "_check_dates_stale"), \
         patch.object(window, "_refresh_table"), \
         patch.object(window, "_set_action_buttons_enabled") as mock_enable:
        window._on_refresh_done(include_art=False)
    mock_enable.assert_called_once_with(True)


def test_on_refresh_done_calls_art_resolve_when_include_art(qtbot):
    window = _make_app(qtbot)
    with patch.object(window, "_check_dates_stale"), \
         patch.object(window, "_refresh_table"), \
         patch.object(window, "_start_art_resolve") as mock_resolve:
        window._on_refresh_done(include_art=True)
    mock_resolve.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_main_window_layout.py::test_fetch_art_button_exists_in_toolbar tests/test_main_window_layout.py::test_on_refresh_done_re_enables_buttons_when_no_art tests/test_main_window_layout.py::test_on_refresh_done_calls_art_resolve_when_include_art -v
```

Expected: FAIL (attribute errors / assertion errors).

- [ ] **Step 3: Update imports in `gui/main_window.py`**

**3a.** Replace the `QWidgets` import (lines 5–8):

```python
from PySide6.QtWidgets import (
    QDialog, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QFrame, QLabel,
)
```

**3b.** Replace the `db` import (line 12):

```python
from db import (init_db, get_songs, get_song_by_id, get_setting, set_setting,
                get_songs_with_art_url, ART_DIR, count_pending_art)
```

**3c.** Replace the `workers` import (line 19):

```python
from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker, ArtFetchWorker, ArtResolveWorker
```

**3d.** Add after the `BatchResultsDialog` import (line 21):

```python
from gui.refresh_mode_dialog import RefreshModeDialog
```

- [ ] **Step 4: Add Fetch Art button in `_build_ui`**

In `_build_ui`, the current block that adds toolbar buttons (after `self._batch_btn` is created) reads:

```python
self._batch_btn = QPushButton("☰ Batch Mode")
self._batch_btn.clicked.connect(self._enter_batch_mode)
self.filter_bar.add_to_toolbar(self._batch_btn)
self.filter_bar.add_to_toolbar(self.filter_bar._settings_btn)
```

Replace with:

```python
self._batch_btn = QPushButton("☰ Batch Mode")
self._batch_btn.clicked.connect(self._enter_batch_mode)

self._fetch_art_btn = QPushButton("⬇ Fetch Art")
self._fetch_art_btn.clicked.connect(self._start_art_resolve)
self.filter_bar.add_to_toolbar(self._fetch_art_btn)
self.filter_bar.add_to_toolbar(self._batch_btn)
self.filter_bar.add_to_toolbar(self.filter_bar._settings_btn)
```

- [ ] **Step 5: Add `_set_action_buttons_enabled` helper**

Add this method to `FuserApp`, after `_check_dates_stale`:

```python
def _set_action_buttons_enabled(self, enabled: bool):
    self.filter_bar.set_refresh_enabled(enabled)
    self._fetch_art_btn.setEnabled(enabled)
```

- [ ] **Step 6: Replace `_start_refresh`**

Replace the entire `_start_refresh` method:

```python
def _start_refresh(self):
    pending = count_pending_art(self.conn)
    include_art = False
    if pending > 0:
        dlg = RefreshModeDialog(pending, parent=self)
        include_art = dlg.exec() == QDialog.DialogCode.Accepted

    self._set_action_buttons_enabled(False)
    worker = RefreshWorker(self.conn)
    worker.status.connect(self.status_bar.set_message)
    worker.error.connect(self.status_bar.set_error)
    worker.error.connect(lambda _: self._set_action_buttons_enabled(True))
    worker.finished.connect(lambda: self._on_refresh_done(include_art))
    self._active_worker = worker
    worker.start()
```

- [ ] **Step 7: Replace `_on_refresh_done`**

```python
def _on_refresh_done(self, include_art: bool = False):
    self.filter_bar.set_updated_label(f"Updated {date.today().isoformat()}")
    self._refresh_table()
    self._check_dates_stale()
    if include_art:
        self._start_art_resolve()
    else:
        self._set_action_buttons_enabled(True)
```

- [ ] **Step 8: Add `_start_art_resolve`**

Add this new method after `_on_refresh_done`:

```python
def _start_art_resolve(self):
    self._set_action_buttons_enabled(False)
    worker = ArtResolveWorker(self.conn)
    worker.status.connect(self.status_bar.set_message)
    worker.error.connect(self.status_bar.set_error)
    worker.error.connect(lambda _: self._set_action_buttons_enabled(True))
    worker.finished.connect(self._start_art_fetch)
    self._art_worker = worker
    worker.start()
```

- [ ] **Step 9: Replace `_start_art_fetch`**

```python
def _start_art_fetch(self):
    songs = get_songs_with_art_url(self.conn)
    uncached = [s for s in songs if not (ART_DIR / f"{s['id']}.jpg").exists()]
    if not uncached:
        self._set_action_buttons_enabled(True)
        self.status_bar.set_idle()
        return
    worker = ArtFetchWorker(uncached)
    worker.status.connect(self.status_bar.set_message)
    worker.art_ready.connect(self._on_art_ready)
    worker.finished.connect(self.status_bar.set_idle)
    worker.finished.connect(lambda: self._set_action_buttons_enabled(True))
    self._art_worker = worker
    worker.start()
```

- [ ] **Step 10: Run the new tests**

```
pytest tests/test_main_window_layout.py -v
```

Expected: all pass (including the 3 pre-existing tests).

- [ ] **Step 11: Run full suite**

```
pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 12: Commit**

```bash
git add gui/main_window.py gui/refresh_mode_dialog.py tests/test_main_window_layout.py
git commit -m "feat: refresh mode dialog, Fetch Art button, split art pipeline"
```
