# PySide6 UI Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the customtkinter `gui/` package with a PySide6 implementation that supports window resizing, virtual scroll (no pagination), and full QSS styling.

**Architecture:** `SongTableModel` (QAbstractTableModel) feeds a `SongTableView` (QTableView) with custom delegates for install status and quality badges. All inter-widget communication goes through PySide6 signals. Background work runs in `QThread` subclasses. One `styles.py` file holds the entire QSS stylesheet.

**Tech Stack:** PySide6 6.x, pytest-qt (testing), existing backend unchanged (db.py, downloader.py, installer.py, sources/)

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `setup.py` | Swap customtkinter → PySide6 dependency |
| Modify | `db.py` | Add optional `limit` param to `get_songs()` |
| Modify | `app.py` | PySide6 entry point |
| Create | `gui/styles.py` | QSS stylesheet string |
| Rewrite | `gui/status_bar.py` | QWidget: progress bar + message label |
| Rewrite | `gui/filter_bar.py` | QWidget: search, dropdowns, BPM, sort, clear (emits `filters_changed`) |
| Rewrite | `gui/song_table.py` | SongTableModel + InstallDelegate + QualityDelegate + SongTableView |
| Rewrite | `gui/detail_panel.py` | QScrollArea: song fields + action buttons (emits signals) |
| Create | `gui/workers.py` | QThread workers: RefreshWorker, DownloadWorker, BatchDownloadWorker |
| Rewrite | `gui/settings_dialog.py` | QDialog: install path setting |
| Rewrite | `gui/batch_results_dialog.py` | QDialog: batch download results list |
| Rewrite | `gui/main_window.py` | QMainWindow: assembles all widgets, connects signals |
| Modify | `tests/test_db.py` | Add test for no-limit get_songs |
| Create | `tests/test_song_table_model.py` | Unit tests for SongTableModel |
| Create | `tests/test_filter_bar.py` | Signal tests for FilterBar |
| Create | `tests/test_status_bar.py` | State tests for StatusBar |
| Create | `tests/test_workers.py` | Worker signal tests with mocking |
| Modify | `tests/test_gui_smoke.py` | Update import smoke test |

---

## Task 1: Dependencies

**Files:**
- Modify: `setup.py`

- [ ] **Step 1: Update setup.py**

Replace the `customtkinter` entry in `install_requires` with `PySide6`:

```python
install_requires=[
    "PySide6>=6.6.0",
    "requests>=2.31.0",
    "beautifulsoup4>=4.12.3",
    "gdown>=5.1.0",
    "patool==4.0.4",
],
```

- [ ] **Step 2: Install dependencies**

```bash
pip install PySide6 pytest-qt
```

Expected: no errors; `python -c "from PySide6.QtWidgets import QApplication; print('ok')"` prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add setup.py
git commit -m "chore: replace customtkinter with PySide6"
```

---

## Task 2: db.py — optional limit for virtual scrolling

**Files:**
- Modify: `db.py:197-221`
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_db.py`:

```python
def test_get_songs_no_limit_returns_all(tmp_path):
    conn = init_db(tmp_path / "test.db")
    songs = [
        {**SONG, "title": f"Song {i}", "link": f"https://drive.google.com/file/d/{i}"}
        for i in range(110)
    ]
    upsert_songs(conn, songs)
    rows = get_songs(conn, {}, limit=0)
    assert len(rows) == 110
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_db.py::test_get_songs_no_limit_returns_all -v
```

Expected: FAIL — `get_songs() takes 2 positional arguments but 3 were given` (or similar).

- [ ] **Step 3: Update get_songs in db.py**

Replace the `get_songs` function (lines 197–221):

```python
def get_songs(conn: sqlite3.Connection, filters: dict, limit: int = 100) -> list[dict]:
    where, params = _build_where_params(filters)

    _ALLOWED_ORDER = {
        "s.artist", "s.title", "s.creator", "s.bpm", "s.year",
        "s.genre", "s.key", "s.source", "s.de_status", "s.quality",
        "s.submit_date",
    }
    order = filters.get("order_by", "s.artist")
    if order not in _ALLOWED_ORDER:
        order = "s.artist"
    direction = "DESC" if filters.get("descending") else "ASC"

    sql = f"""
        SELECT s.*, {_IS_DEFINITIVE} AS is_definitive,
               i.pak_path, i.sig_path, i.installed_at
        FROM songs s
        LEFT JOIN installed i ON i.song_id = s.id
        WHERE {' AND '.join(where)}
        ORDER BY {order} {direction}, s.id DESC
    """
    if limit > 0:
        offset = filters.get("offset", 0)
        sql += "\n        LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    return [dict(r) for r in conn.execute(sql, params).fetchall()]
```

- [ ] **Step 4: Run all db tests**

```bash
pytest tests/test_db.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add optional limit param to get_songs for virtual scroll"
```

---

## Task 3: styles.py — QSS stylesheet

**Files:**
- Create: `gui/styles.py`

No automated test — visual output verified when running the app in Task 11.

- [ ] **Step 1: Create gui/styles.py**

```python
APP_STYLE = """
QMainWindow, QDialog {
    background-color: #1c1c1c;
    color: #e0e0e0;
}

QWidget {
    background-color: #1c1c1c;
    color: #e0e0e0;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

/* ── Toolbar / filter frames ── */
QFrame#toolbar, QFrame#filterbar, QFrame#batchbar {
    background-color: #212121;
    border-bottom: 1px solid #2e2e2e;
}

/* ── Inputs ── */
QLineEdit {
    background-color: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    color: #e0e0e0;
    padding: 4px 8px;
}
QLineEdit:focus {
    border-color: #2563eb;
}
QLineEdit[placeholderText] {
    color: #555555;
}

/* ── Dropdowns ── */
QComboBox {
    background-color: #282828;
    border: 1px solid #383838;
    border-radius: 4px;
    color: #cccccc;
    padding: 4px 8px;
    min-width: 80px;
}
QComboBox:focus {
    border-color: #2563eb;
}
QComboBox::drop-down {
    border: none;
    width: 18px;
}
QComboBox::down-arrow {
    width: 8px;
    height: 8px;
    border: 2px solid #666;
    border-top: none;
    border-right: none;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #282828;
    border: 1px solid #383838;
    color: #cccccc;
    selection-background-color: #1e3a5f;
}

/* ── Buttons ── */
QPushButton {
    background-color: #2e2e2e;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    color: #bbbbbb;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #383838;
    border-color: #4a4a4a;
}
QPushButton:pressed {
    background-color: #242424;
}
QPushButton:disabled {
    color: #555555;
    border-color: #2a2a2a;
}

QPushButton#primaryBtn {
    background-color: #1d4ed8;
    border-color: #2563eb;
    color: #ffffff;
}
QPushButton#primaryBtn:hover {
    background-color: #2563eb;
}
QPushButton#primaryBtn:disabled {
    background-color: #1a2a50;
    color: #555;
}

QPushButton#downloadBtn {
    background-color: #166534;
    border-color: #15803d;
    color: #86efac;
}
QPushButton#downloadBtn:hover {
    background-color: #15803d;
}
QPushButton#downloadBtn:disabled {
    background-color: #0f2a1a;
    color: #555;
}

QPushButton#dangerBtn {
    background-color: #2a2a2a;
    border-color: #3f1515;
    color: #f87171;
}
QPushButton#dangerBtn:hover {
    background-color: #3a1a1a;
}
QPushButton#dangerBtn:disabled {
    color: #555;
    border-color: #2a2a2a;
}

QPushButton#manualBtn {
    background-color: #2a2a2a;
    border-color: #3f2a00;
    color: #fbbf24;
}
QPushButton#manualBtn:hover {
    background-color: #3a2a00;
}

/* ── Table ── */
QTableView {
    background-color: #1c1c1c;
    alternate-background-color: #212121;
    border: none;
    gridline-color: transparent;
    selection-background-color: #1e3a5f;
    selection-color: #93c5fd;
    outline: none;
}
QTableView::item {
    padding: 0 6px;
    border: none;
}
QTableView::item:selected {
    background-color: #1e3a5f;
    color: #93c5fd;
}

QHeaderView::section {
    background-color: #222222;
    color: #666666;
    border: none;
    border-bottom: 2px solid #2a2a2a;
    padding: 6px 8px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── Scrollbars ── */
QScrollBar:vertical {
    background: #1c1c1c;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3a3a3a;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #4a4a4a;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #1c1c1c;
    height: 6px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #3a3a3a;
    border-radius: 3px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Status bar ── */
QStatusBar {
    background-color: #161616;
    border-top: 1px solid #282828;
    color: #666666;
    font-size: 11px;
}
QStatusBar QLabel {
    background-color: transparent;
    padding: 0 4px;
}

QProgressBar {
    background-color: #2a2a2a;
    border: none;
    border-radius: 3px;
    max-height: 4px;
    text-visible: false;
}
QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 3px;
}

/* ── Labels ── */
QLabel#sectionTitle {
    color: #555555;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#updatedLabel {
    color: #555555;
    font-size: 11px;
}
QLabel#manualLabel {
    color: #f4a261;
}
QLabel#errorLabel {
    color: #e76f51;
}
QLabel#successLabel {
    color: #52b788;
}

/* ── Splitter ── */
QSplitter::handle {
    background-color: #2a2a2a;
    width: 1px;
}

/* ── Detail panel ── */
QFrame#detailPanel {
    background-color: #1a1a1a;
    border-left: 1px solid #272727;
}
"""
```

- [ ] **Step 2: Commit**

```bash
git add gui/styles.py
git commit -m "feat: add PySide6 QSS stylesheet"
```

---

## Task 4: gui/status_bar.py

**Files:**
- Rewrite: `gui/status_bar.py`
- Create: `tests/test_status_bar.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_status_bar.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.status_bar import StatusBar


def test_initial_state(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    assert bar._lbl.text() == "Ready"
    assert not bar._progress.isVisible()


def test_set_message(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.set_message("Scanning…")
    assert bar._lbl.text() == "Scanning…"
    assert not bar._progress.isVisible()


def test_start_download_shows_progress(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.start_download("Get Lucky")
    assert "Get Lucky" in bar._lbl.text()
    assert bar._progress.isVisible()
    assert bar._progress.value() == 0


def test_set_progress_updates_bar(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.start_download("Get Lucky")
    bar.set_progress(0.5)
    assert bar._progress.value() == 50


def test_set_done_hides_progress_after_delay(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.set_done("Get Lucky")
    assert "Get Lucky" in bar._lbl.text()
    assert bar._progress.value() == 100


def test_set_error(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.set_error("Download failed")
    assert "Download failed" in bar._lbl.text()
    assert not bar._progress.isVisible()


def test_set_idle(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.start_download("test")
    bar.set_idle()
    assert bar._lbl.text() == "Ready"
    assert not bar._progress.isVisible()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_status_bar.py -v
```

Expected: FAIL — `ModuleNotFoundError` or `ImportError` on PySide6 / new StatusBar.

- [ ] **Step 3: Rewrite gui/status_bar.py**

```python
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import QTimer


class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self._lbl = QLabel("Ready")
        layout.addWidget(self._lbl)
        layout.addStretch()

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setFixedWidth(200)
        self._progress.setTextVisible(False)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self.set_idle)

    def start_download(self, title: str):
        self._lbl.setText(f"Downloading: {title}")
        self._lbl.setProperty("class", "")
        self._progress.setValue(0)
        self._progress.show()

    def set_progress(self, value: float):
        self._progress.setValue(int(max(0.0, min(1.0, value)) * 100))

    def set_done(self, title: str):
        self._lbl.setText(f"Installed: {title}")
        self._progress.setValue(100)
        self._idle_timer.start(3000)

    def set_error(self, msg: str):
        self._lbl.setText(f"Error: {msg}")
        self._progress.hide()

    def set_idle(self):
        self._idle_timer.stop()
        self._lbl.setText("Ready")
        self._progress.hide()
        self._progress.setValue(0)

    def set_message(self, text: str):
        self._lbl.setText(text)
        self._progress.hide()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_status_bar.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/status_bar.py tests/test_status_bar.py
git commit -m "feat: rewrite StatusBar in PySide6"
```

---

## Task 5: gui/filter_bar.py

**Files:**
- Create: `gui/filter_bar.py`
- Create: `tests/test_filter_bar.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_filter_bar.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.filter_bar import FilterBar


def test_default_filters(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    f = bar.get_filters()
    assert f["search"] == ""
    assert f["order_by"] == "s.artist"
    assert f.get("descending") is None or f.get("descending") is False
    assert "source" not in f
    assert "quality" not in f
    assert "installed" not in f


def test_search_emits_filters_changed(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    with qtbot.waitSignal(bar.filters_changed, timeout=1000) as blocker:
        bar._search.setText("Nirvana")
    assert blocker.args[0]["search"] == "Nirvana"


def test_source_filter_included_when_set(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    bar._source.setCurrentText("fucuco_main")
    f = bar.get_filters()
    assert f["source"] == "fucuco_main"


def test_source_filter_excluded_when_all(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    bar._source.setCurrentText("All Sources")
    f = bar.get_filters()
    assert "source" not in f


def test_sort_newest_first(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    bar._sort.setCurrentText("Newest First")
    f = bar.get_filters()
    assert f["order_by"] == "s.submit_date"
    assert f["descending"] is True


def test_bpm_range(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    bar._bpm_min.setText("100")
    bar._bpm_max.setText("140")
    f = bar.get_filters()
    assert f["bpm_min"] == 100
    assert f["bpm_max"] == 140


def test_invalid_bpm_ignored(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    bar._bpm_min.setText("abc")
    f = bar.get_filters()
    assert "bpm_min" not in f


def test_clear_resets_all_fields(qtbot):
    bar = FilterBar()
    qtbot.addWidget(bar)
    bar._search.setText("test")
    bar._source.setCurrentText("fucuco_main")
    bar._bpm_min.setText("100")
    bar.clear()
    f = bar.get_filters()
    assert f["search"] == ""
    assert "source" not in f
    assert "bpm_min" not in f
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_filter_bar.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create gui/filter_bar.py**

```python
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFrame,
)
from PySide6.QtCore import Signal, Qt

_SORT_MAP = {
    "Artist A–Z":   ("s.artist",      False),
    "Newest First": ("s.submit_date", True),
    "BPM ↑":        ("s.bpm",         False),
    "BPM ↓":        ("s.bpm",         True),
}

_INSTALLED_MAP = {
    "Installed":     "installed",
    "Not Installed": "not_installed",
}


class FilterBar(QWidget):
    filters_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()
        self._connect()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Row 1: search + actions ──
        top = QFrame()
        top.setObjectName("toolbar")
        self._top_layout = QHBoxLayout(top)
        top_layout = self._top_layout
        top_layout.setContentsMargins(8, 6, 8, 6)
        top_layout.setSpacing(6)

        top_layout.addWidget(QLabel("Search"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Artist, title, genre…")
        self._search.setFixedWidth(240)
        top_layout.addWidget(self._search)
        top_layout.addStretch()

        self._updated_lbl = QLabel("")
        self._updated_lbl.setObjectName("updatedLabel")
        top_layout.addWidget(self._updated_lbl)

        self._refresh_btn = QPushButton("Refresh Sources")
        self._refresh_btn.setObjectName("primaryBtn")
        top_layout.addWidget(self._refresh_btn)

        self._settings_btn = QPushButton("⚙ Settings")
        top_layout.addWidget(self._settings_btn)

        outer.addWidget(top)

        # ── Row 2: filters ──
        fbar = QFrame()
        fbar.setObjectName("filterbar")
        fbar_layout = QHBoxLayout(fbar)
        fbar_layout.setContentsMargins(8, 4, 8, 4)
        fbar_layout.setSpacing(4)

        fbar_layout.addWidget(QLabel("Source"))
        self._source = QComboBox()
        self._source.addItems(["All Sources", "fucuco_main", "fucuco_vgm", "fusersoundlab"])
        fbar_layout.addWidget(self._source)

        fbar_layout.addWidget(QLabel("Quality"))
        self._quality = QComboBox()
        self._quality.addItems(["All Quality", "Official", "Definitive", "Complete", "Other"])
        fbar_layout.addWidget(self._quality)

        fbar_layout.addWidget(QLabel("Status"))
        self._installed = QComboBox()
        self._installed.addItems(["All", "Installed", "Not Installed"])
        fbar_layout.addWidget(self._installed)

        fbar_layout.addWidget(QLabel("Genre"))
        self._genre = QLineEdit()
        self._genre.setPlaceholderText("e.g. Rock")
        self._genre.setFixedWidth(90)
        fbar_layout.addWidget(self._genre)

        fbar_layout.addWidget(QLabel("BPM"))
        self._bpm_min = QLineEdit()
        self._bpm_min.setPlaceholderText("min")
        self._bpm_min.setFixedWidth(52)
        fbar_layout.addWidget(self._bpm_min)
        fbar_layout.addWidget(QLabel("–"))
        self._bpm_max = QLineEdit()
        self._bpm_max.setPlaceholderText("max")
        self._bpm_max.setFixedWidth(52)
        fbar_layout.addWidget(self._bpm_max)

        fbar_layout.addWidget(QLabel("Sort"))
        self._sort = QComboBox()
        self._sort.addItems(["Artist A–Z", "Newest First", "BPM ↑", "BPM ↓"])
        fbar_layout.addWidget(self._sort)

        fbar_layout.addStretch()

        clear_btn = QPushButton("✕ Clear Filters")
        clear_btn.clicked.connect(self.clear)
        fbar_layout.addWidget(clear_btn)

        outer.addWidget(fbar)

    def add_to_toolbar(self, widget):
        """Append a widget to the right end of the top toolbar row."""
        self._top_layout.addWidget(widget)

    def _connect(self):
        self._search.textChanged.connect(self._emit)
        self._source.currentIndexChanged.connect(self._emit)
        self._quality.currentIndexChanged.connect(self._emit)
        self._installed.currentIndexChanged.connect(self._emit)
        self._genre.textChanged.connect(self._emit)
        self._bpm_min.textChanged.connect(self._emit)
        self._bpm_max.textChanged.connect(self._emit)
        self._sort.currentIndexChanged.connect(self._emit)

    def _emit(self):
        self.filters_changed.emit(self.get_filters())

    def get_filters(self) -> dict:
        f: dict = {"search": self._search.text()}

        src = self._source.currentText()
        if src != "All Sources":
            f["source"] = src

        q = self._quality.currentText()
        if q != "All Quality":
            f["quality"] = q

        installed_val = _INSTALLED_MAP.get(self._installed.currentText())
        if installed_val:
            f["installed"] = installed_val

        genre = self._genre.text().strip()
        if genre:
            f["genre"] = genre

        try:
            if self._bpm_min.text():
                f["bpm_min"] = int(self._bpm_min.text())
        except ValueError:
            pass
        try:
            if self._bpm_max.text():
                f["bpm_max"] = int(self._bpm_max.text())
        except ValueError:
            pass

        order_by, descending = _SORT_MAP.get(self._sort.currentText(), ("s.artist", False))
        f["order_by"] = order_by
        if descending:
            f["descending"] = True

        return f

    def clear(self):
        for widget in (self._search, self._genre, self._bpm_min, self._bpm_max):
            widget.blockSignals(True)
            widget.clear()
            widget.blockSignals(False)
        for combo in (self._source, self._quality, self._installed, self._sort):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self._emit()

    def set_updated_label(self, text: str):
        self._updated_lbl.setText(text)

    def set_refresh_enabled(self, enabled: bool):
        self._refresh_btn.setEnabled(enabled)
        self._refresh_btn.setText("Refreshing…" if not enabled else "Refresh Sources")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_filter_bar.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/filter_bar.py tests/test_filter_bar.py
git commit -m "feat: create PySide6 FilterBar with filters_changed signal"
```

---

## Task 6: gui/song_table.py — model, delegates, view

**Files:**
- Rewrite: `gui/song_table.py`
- Create: `tests/test_song_table_model.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_song_table_model.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtCore import Qt
from gui.song_table import SongTableModel, COL_TITLE, COL_ARTIST, COL_BPM, COL_QUALITY, COL_SOURCE, COL_INSTALLED

SONGS = [
    {"id": 1, "title": "Get Lucky", "artist": "Daft Punk", "bpm": 116,
     "quality": "Complete", "source": "fucuco_main", "pak_path": "/some/path.pak"},
    {"id": 2, "title": "Come As You Are", "artist": "Nirvana", "bpm": 120,
     "quality": "Definitive", "source": "fusersoundlab", "pak_path": None},
]


def test_initial_row_count_is_zero(qtbot):
    model = SongTableModel()
    assert model.rowCount() == 0


def test_reset_updates_row_count(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    assert model.rowCount() == 2


def test_column_count(qtbot):
    model = SongTableModel()
    assert model.columnCount() == 6


def test_data_title(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(0, COL_TITLE)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "Get Lucky"


def test_data_artist(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(0, COL_ARTIST)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "Daft Punk"


def test_data_bpm(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(0, COL_BPM)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "116"


def test_data_quality(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(0, COL_QUALITY)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "Complete"


def test_data_source(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(0, COL_SOURCE)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "fucuco_main"


def test_data_installed_returns_none_for_display(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(0, COL_INSTALLED)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) is None


def test_user_role_returns_song_dict(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(1, COL_TITLE)
    song = model.data(idx, Qt.ItemDataRole.UserRole)
    assert song["artist"] == "Nirvana"


def test_get_row(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    assert model.get_row(0)["title"] == "Get Lucky"
    assert model.get_row(1)["artist"] == "Nirvana"


def test_header_data(qtbot):
    model = SongTableModel()
    assert model.headerData(COL_TITLE, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "Title"
    assert model.headerData(COL_ARTIST, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "Artist"


def test_reset_replaces_rows(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    model.reset([SONGS[0]])
    assert model.rowCount() == 1
    assert model.get_row(0)["title"] == "Get Lucky"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_song_table_model.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Rewrite gui/song_table.py**

```python
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import QTableView, QStyledItemDelegate, QAbstractItemView, QStyle
from PySide6.QtGui import QPainter, QColor, QFont, QBrush

COL_INSTALLED = 0
COL_TITLE = 1
COL_ARTIST = 2
COL_BPM = 3
COL_QUALITY = 4
COL_SOURCE = 5
NUM_COLS = 6

_HEADERS = ["", "Title", "Artist", "BPM", "Quality", "Source"]

_QUALITY_COLORS = {
    "Official":   ("#1d3557", "#74b3f0"),
    "Definitive": ("#2d2a00", "#fde68a"),
    "Complete":   ("#1a2e1a", "#86efac"),
    "Other":      ("#2a2a2a", "#888888"),
}


class SongTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []

    def reset(self, rows: list[dict]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def get_row(self, index: int) -> dict:
        return self._rows[index]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return NUM_COLS

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.UserRole:
            return row

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_INSTALLED:
                return None
            if col == COL_TITLE:
                return row.get("title", "")
            if col == COL_ARTIST:
                return row.get("artist", "")
            if col == COL_BPM:
                bpm = row.get("bpm")
                return str(bpm) if bpm else ""
            if col == COL_QUALITY:
                return row.get("quality", "")
            if col == COL_SOURCE:
                return row.get("source", "")

        if role == Qt.ItemDataRole.BackgroundRole:
            if row.get("pak_path") and not (index.column() == COL_INSTALLED):
                return QBrush(QColor("#1a2e1a"))

        return None

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _HEADERS[section]
        return None


class InstallDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index: QModelIndex):
        song = index.data(Qt.ItemDataRole.UserRole)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#1e3a5f"))
        else:
            painter.fillRect(option.rect, option.backgroundBrush if option.backgroundBrush.style() != Qt.BrushStyle.NoBrush else QColor("#1c1c1c"))
        installed = bool(song.get("pak_path")) if song else False
        cx = option.rect.center().x()
        cy = option.rect.center().y()
        radius = 4
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        if installed:
            painter.setBrush(QColor("#22c55e"))
        else:
            painter.setBrush(QColor("#3a3a3a"))
        from PySide6.QtCore import QRect
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
        painter.restore()


class QualityDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index: QModelIndex):
        quality = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#1e3a5f"))
        else:
            bg = index.data(Qt.ItemDataRole.BackgroundRole)
            if bg:
                painter.fillRect(option.rect, bg)
            else:
                painter.fillRect(option.rect, QColor("#1c1c1c"))
        if not quality:
            return
        bg_hex, fg_hex = _QUALITY_COLORS.get(quality, ("#2a2a2a", "#888888"))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(quality)
        badge_h = option.rect.height() - 8
        badge_w = text_width + 12
        bx = option.rect.x() + 4
        by = option.rect.y() + 4
        from PySide6.QtCore import QRectF
        painter.setBrush(QColor(bg_hex))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(bx, by, badge_w, badge_h), 3, 3)
        painter.setPen(QColor(fg_hex))
        f = QFont(painter.font())
        f.setPointSize(10)
        f.setBold(True)
        painter.setFont(f)
        from PySide6.QtCore import QRect
        painter.drawText(QRect(bx, by, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, quality)
        painter.restore()


class SongTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.horizontalHeader().setStretchLastSection(True)
        self.setWordWrap(False)
        self.verticalHeader().setDefaultSectionSize(28)

    def set_model(self, model: SongTableModel):
        self.setModel(model)
        self.setItemDelegateForColumn(COL_INSTALLED, InstallDelegate(self))
        self.setItemDelegateForColumn(COL_QUALITY, QualityDelegate(self))
        self.setColumnWidth(COL_INSTALLED, 28)
        self.setColumnWidth(COL_BPM, 60)
        self.setColumnWidth(COL_QUALITY, 100)
        self.setColumnWidth(COL_SOURCE, 110)
        self.horizontalHeader().setStretchLastSection(False)
        self.setColumnWidth(COL_ARTIST, 160)

    def get_selected_songs(self) -> list[dict]:
        m = self.model()
        if m is None:
            return []
        return [m.get_row(idx.row()) for idx in self.selectionModel().selectedRows()]

    def select_all(self):
        self.selectAll()

    def deselect_all(self):
        self.clearSelection()

    def set_batch_mode(self, enabled: bool):
        if enabled:
            self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        else:
            self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_song_table_model.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/song_table.py tests/test_song_table_model.py
git commit -m "feat: rewrite SongTable as PySide6 QAbstractTableModel + QTableView"
```

---

## Task 7: gui/detail_panel.py

**Files:**
- Rewrite: `gui/detail_panel.py`
- Create: `tests/test_detail_panel.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_detail_panel.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.detail_panel import DetailPanel

SONG = {
    "id": 1, "title": "Get Lucky", "artist": "Daft Punk", "bpm": 116,
    "key": "A Minor", "genre": "Pop", "year": 2013,
    "submit_date": "2024/03/01", "source": "fucuco_main",
    "de_status": "Eligible", "complete": "C", "complete_notes": "",
    "origin": None, "stream_opt": 1,
    "link": "https://drive.google.com/file/d/abc",
    "pak_path": None, "quality": "Complete",
}

INSTALLED_SONG = {**SONG, "pak_path": "/path/to/get_lucky.pak"}


def test_initial_state_no_song(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    assert panel._song is None


def test_show_populates_title(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    assert panel._song == SONG
    assert panel._labels["title"].text() == "Get Lucky"


def test_show_populates_artist(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    assert panel._labels["artist"].text() == "Daft Punk"


def test_download_btn_enabled_when_not_installed(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    assert panel._dl_btn.isEnabled()


def test_download_btn_disabled_when_installed(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(INSTALLED_SONG)
    assert not panel._dl_btn.isEnabled()


def test_uninstall_btn_enabled_when_installed(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(INSTALLED_SONG)
    assert panel._un_btn.isEnabled()


def test_uninstall_btn_disabled_when_not_installed(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    assert not panel._un_btn.isEnabled()


def test_download_requested_signal(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    with qtbot.waitSignal(panel.download_requested, timeout=1000) as blocker:
        panel._dl_btn.click()
    assert blocker.args[0]["title"] == "Get Lucky"


def test_uninstall_requested_signal(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(INSTALLED_SONG)
    with qtbot.waitSignal(panel.uninstall_requested, timeout=1000) as blocker:
        panel._un_btn.click()
    assert blocker.args[0]["id"] == 1


def test_stream_opt_displays_yes_no(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    assert panel._labels["stream_opt"].text() == "Yes"
    panel.show({**SONG, "stream_opt": 0})
    assert panel._labels["stream_opt"].text() == "No"


def test_complete_field_mapped(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show({**SONG, "complete": "D"})
    assert panel._labels["complete"].text() == "Definitive"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_detail_panel.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Rewrite gui/detail_panel.py**

```python
import webbrowser
from pathlib import Path
from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QFrame,
)
from PySide6.QtCore import Signal, Qt

_FIELDS = [
    ("artist",         "Artist"),
    ("title",          "Title"),
    ("creator",        "Creator"),
    ("bpm",            "BPM"),
    ("key",            "Key"),
    ("genre",          "Genre"),
    ("year",           "Year"),
    ("submit_date",    "Date"),
    ("source",         "Source"),
    ("de_status",      "DE Status"),
    ("complete",       "Complete"),
    ("complete_notes", "Notes"),
    ("origin",         "Origin"),
    ("stream_opt",     "Stream-Opt"),
]


class DetailPanel(QScrollArea):
    download_requested = Signal(object)
    uninstall_requested = Signal(object)
    manual_install_requested = Signal(object, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._song: dict | None = None
        self.setWidgetResizable(True)
        self.setObjectName("detailPanel")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._build()

    def _build(self):
        container = QWidget()
        self.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        # Header section
        header = QFrame()
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 12)
        h_layout.setSpacing(2)
        self._title_lbl = QLabel("—")
        self._title_lbl.setStyleSheet("font-size: 16px; font-weight: 600; color: #e8e8e8;")
        self._title_lbl.setWordWrap(True)
        self._artist_lbl = QLabel("—")
        self._artist_lbl.setStyleSheet("font-size: 13px; color: #2563eb; font-weight: 500;")
        h_layout.addWidget(self._title_lbl)
        h_layout.addWidget(self._artist_lbl)
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #272727;")
        layout.addWidget(sep)

        # Fields section
        fields_widget = QWidget()
        fields_layout = QVBoxLayout(fields_widget)
        fields_layout.setContentsMargins(0, 8, 0, 8)
        fields_layout.setSpacing(5)

        self._labels: dict[str, QLabel] = {}
        for field, label in _FIELDS:
            if field in ("artist", "title"):
                continue
            row = QHBoxLayout()
            key_lbl = QLabel(f"{label}")
            key_lbl.setStyleSheet("font-size: 11px; color: #666; min-width: 80px;")
            key_lbl.setFixedWidth(90)
            val_lbl = QLabel("—")
            val_lbl.setStyleSheet("font-size: 12px; color: #c0c0c0;")
            val_lbl.setWordWrap(True)
            self._labels[field] = val_lbl
            row.addWidget(key_lbl)
            row.addWidget(val_lbl)
            fields_layout.addLayout(row)

        # Link row
        link_row = QHBoxLayout()
        link_key = QLabel("Link")
        link_key.setStyleSheet("font-size: 11px; color: #666; min-width: 80px;")
        link_key.setFixedWidth(90)
        self._link_btn = QPushButton("—")
        self._link_btn.setFlat(True)
        self._link_btn.setStyleSheet("color: #6ab0f5; text-align: left; padding: 0;")
        self._link_btn.clicked.connect(self._open_link)
        link_row.addWidget(link_key)
        link_row.addWidget(self._link_btn)
        fields_layout.addLayout(link_row)

        self._path_lbl = QLabel("")
        self._path_lbl.setStyleSheet("font-size: 10px; color: #555; padding-top: 4px;")
        self._path_lbl.setWordWrap(True)
        fields_layout.addWidget(self._path_lbl)

        layout.addWidget(fields_widget)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #242424;")
        layout.addWidget(sep2)

        # Actions section
        actions = QWidget()
        a_layout = QVBoxLayout(actions)
        a_layout.setContentsMargins(0, 10, 0, 0)
        a_layout.setSpacing(6)

        self._dl_btn = QPushButton("Download && Install")
        self._dl_btn.setObjectName("primaryBtn")
        self._dl_btn.clicked.connect(self._download)
        a_layout.addWidget(self._dl_btn)

        self._mark_btn = QPushButton("Mark as Installed (browse .pak…)")
        self._mark_btn.setObjectName("manualBtn")
        self._mark_btn.clicked.connect(self._browse_manual_install)
        a_layout.addWidget(self._mark_btn)

        self._un_btn = QPushButton("Uninstall")
        self._un_btn.setObjectName("dangerBtn")
        self._un_btn.clicked.connect(self._uninstall)
        a_layout.addWidget(self._un_btn)

        self._manual_lbl = QLabel("")
        self._manual_lbl.setObjectName("manualLabel")
        self._manual_lbl.setWordWrap(True)
        a_layout.addWidget(self._manual_lbl)

        layout.addWidget(actions)
        layout.addStretch()

        self._sync_buttons()

    def show(self, song: dict):
        self._song = song
        self._manual_lbl.setText("")
        self._title_lbl.setText(song.get("title", "—"))
        self._artist_lbl.setText(song.get("artist", "—"))

        for field, lbl in self._labels.items():
            val = song.get(field)
            if field == "stream_opt":
                text = "Yes" if val else "No"
            elif field == "complete":
                text = {"D": "Definitive", "C": "Complete"}.get(str(val or ""), str(val or "—"))
            else:
                text = str(val) if val not in (None, "") else "—"
            lbl.setText(text)

        link = song.get("link", "")
        self._link_btn.setText((link[:38] + "…") if len(link) > 38 else link or "—")
        self._path_lbl.setText(
            f"Installed: {song['pak_path']}" if song.get("pak_path") else "")
        self._sync_buttons()

    def show_manual_link(self, url: str):
        self._manual_lbl.setText(
            "Manual download required.\nClick the link above to open in browser.")

    def clear(self):
        self._song = None
        self._title_lbl.setText("—")
        self._artist_lbl.setText("—")
        for lbl in self._labels.values():
            lbl.setText("—")
        self._link_btn.setText("—")
        self._path_lbl.setText("")
        self._manual_lbl.setText("")
        self._sync_buttons()

    def _sync_buttons(self):
        if not self._song:
            self._dl_btn.setEnabled(False)
            self._mark_btn.setEnabled(False)
            self._un_btn.setEnabled(False)
            return
        installed = bool(self._song.get("pak_path"))
        self._dl_btn.setEnabled(not installed)
        self._mark_btn.setEnabled(not installed)
        self._un_btn.setEnabled(installed)

    def _open_link(self):
        if self._song:
            link = self._song.get("link", "")
            if link:
                webbrowser.open(link)

    def _download(self):
        if self._song:
            self._dl_btn.setEnabled(False)
            self.download_requested.emit(self._song)

    def _browse_manual_install(self):
        if not self._song:
            return
        self._manual_lbl.setText("")
        pak_path, _ = QFileDialog.getOpenFileName(
            self, "Select .pak file to install", "",
            "PAK files (*.pak);;All files (*.*)"
        )
        if not pak_path:
            return
        pak = Path(pak_path)
        sig_candidate = pak.with_suffix(".sig")
        sig = sig_candidate if sig_candidate.exists() else None
        self.manual_install_requested.emit(self._song, pak, sig)

    def _uninstall(self):
        if self._song:
            self.uninstall_requested.emit(self._song)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_detail_panel.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/detail_panel.py tests/test_detail_panel.py
git commit -m "feat: rewrite DetailPanel in PySide6 with typed signals"
```

---

## Task 8: gui/workers.py — QThread workers

**Files:**
- Create: `gui/workers.py`
- Create: `tests/test_workers.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_workers.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock
from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker


def test_refresh_worker_emits_finished(qtbot, tmp_path):
    conn = MagicMock()
    worker = RefreshWorker(conn)
    mock_songs = [{"title": "A"}, {"title": "B"}]
    with patch("gui.workers.fetch_fucuco", return_value=[mock_songs[0]]), \
         patch("gui.workers.fetch_fsl", return_value=[mock_songs[1]]), \
         patch("gui.workers.upsert_songs") as mock_upsert:
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()
        mock_upsert.assert_called_once()


def test_refresh_worker_emits_error_on_exception(qtbot):
    conn = MagicMock()
    worker = RefreshWorker(conn)
    with patch("gui.workers.fetch_fucuco", side_effect=RuntimeError("network error")):
        with qtbot.waitSignal(worker.error, timeout=3000) as blocker:
            worker.start()
    assert "network error" in blocker.args[0]


def test_download_worker_emits_progress(qtbot):
    conn = MagicMock()
    song = {"id": 1, "title": "Get Lucky", "link": "http://example.com/song",
            "artist": "Daft Punk"}
    install_dir = Path("/fake/dir")
    mock_result = MagicMock()
    mock_result.status = "ok"

    progress_values = []

    with patch("gui.workers.download", return_value=mock_result) as mock_dl, \
         patch("gui.workers.install_pairs"):
        worker = DownloadWorker(song, install_dir, conn)
        worker.progress.connect(lambda v: progress_values.append(v))
        with qtbot.waitSignal(worker.done, timeout=3000):
            worker.start()


def test_download_worker_emits_manual_on_manual_status(qtbot):
    conn = MagicMock()
    song = {"id": 1, "title": "Get Lucky", "link": "http://example.com", "artist": "Daft Punk"}
    mock_result = MagicMock()
    mock_result.status = "manual"
    mock_result.raw_url = "http://example.com/manual"

    with patch("gui.workers.download", return_value=mock_result):
        worker = DownloadWorker(song, Path("/fake"), conn)
        with qtbot.waitSignal(worker.manual, timeout=3000) as blocker:
            worker.start()
    assert blocker.args[0] == "http://example.com/manual"


def test_download_worker_emits_error_on_error_status(qtbot):
    conn = MagicMock()
    song = {"id": 1, "title": "Get Lucky", "link": "http://example.com", "artist": "Daft Punk"}
    mock_result = MagicMock()
    mock_result.status = "error"
    mock_result.error_msg = "404 not found"

    with patch("gui.workers.download", return_value=mock_result):
        worker = DownloadWorker(song, Path("/fake"), conn)
        with qtbot.waitSignal(worker.error, timeout=3000) as blocker:
            worker.start()
    assert "404" in blocker.args[0]


def test_batch_worker_emits_finished_with_results(qtbot):
    conn = MagicMock()
    songs = [
        {"id": 1, "title": "A", "link": "http://a.com", "artist": "ArtA"},
        {"id": 2, "title": "B", "link": "http://b.com", "artist": "ArtB"},
    ]
    mock_result = MagicMock()
    mock_result.status = "ok"

    with patch("gui.workers.download", return_value=mock_result), \
         patch("gui.workers.install_pairs"):
        worker = BatchDownloadWorker(songs, Path("/fake"), conn)
        with qtbot.waitSignal(worker.finished, timeout=5000) as blocker:
            worker.start()
    results = blocker.args[0]
    assert len(results) == 2
    assert all(r["status"] == "ok" for r in results)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_workers.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create gui/workers.py**

```python
from pathlib import Path
from PySide6.QtCore import QThread, Signal

from db import upsert_songs
from downloader import download
from installer import install_pairs
from sources.fucuco import fetch_all as fetch_fucuco
from sources.fusersoundlab import fetch_all as fetch_fsl


class RefreshWorker(QThread):
    finished = Signal()
    error = Signal(str)

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn

    def run(self):
        try:
            songs = fetch_fucuco() + fetch_fsl()
            upsert_songs(self._conn, songs)
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc) or type(exc).__name__)


class DownloadWorker(QThread):
    progress = Signal(float)
    done = Signal(str)
    manual = Signal(str)
    error = Signal(str)

    def __init__(self, song: dict, install_dir: Path, conn, parent=None):
        super().__init__(parent)
        self._song = song
        self._install_dir = install_dir
        self._conn = conn

    def run(self):
        result = download(
            self._song["link"],
            progress_cb=lambda p: self.progress.emit(p),
        )
        if result.status == "ok":
            try:
                install_pairs(result, self._song["id"], self._song["artist"],
                              self._install_dir, self._conn)
                self.done.emit(self._song["title"])
            except Exception as exc:
                self.error.emit(str(exc) or "Install failed")
        elif result.status == "manual":
            self.manual.emit(result.raw_url or "")
        else:
            self.error.emit(result.error_msg or "Unknown error")


class BatchDownloadWorker(QThread):
    item_progress = Signal(str)
    finished = Signal(list)

    def __init__(self, songs: list[dict], install_dir: Path, conn, parent=None):
        super().__init__(parent)
        self._songs = songs
        self._install_dir = install_dir
        self._conn = conn

    def run(self):
        results: list[dict] = []
        n = len(self._songs)
        for i, song in enumerate(self._songs):
            self.item_progress.emit(f"[{i + 1}/{n}] Downloading: {song['title']}")
            result = download(song["link"])
            entry: dict = {"song": song}
            if result.status == "ok":
                try:
                    install_pairs(result, song["id"], song["artist"],
                                  self._install_dir, self._conn)
                    entry["status"] = "ok"
                    entry["message"] = "Installed"
                except Exception as exc:
                    entry["status"] = "error"
                    entry["message"] = str(exc) or "Install failed"
            elif result.status == "manual":
                entry["status"] = "manual"
                entry["message"] = "Manual download required"
            else:
                entry["status"] = "error"
                entry["message"] = result.error_msg or "Unknown error"
            results.append(entry)
        self.finished.emit(results)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_workers.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/workers.py tests/test_workers.py
git commit -m "feat: add PySide6 QThread workers for refresh, download, batch"
```

---

## Task 9: gui/settings_dialog.py

**Files:**
- Rewrite: `gui/settings_dialog.py`

No separate test file — settings dialog behavior is verified in the smoke test (Task 12).

- [ ] **Step 1: Create gui/settings_dialog.py**

```python
import threading
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Signal

from db import get_setting, set_setting
from installer import scan_and_sync


class SettingsDialog(QDialog):
    path_saved = Signal(Path)

    def __init__(self, current_path: Path, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("Settings")
        self.setFixedSize(520, 200)
        self._build(current_path)

    def _build(self, current_path: Path):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        layout.addWidget(QLabel("<b>Song Install Directory</b>"))
        sub = QLabel("Choose where .pak/.sig files are installed:")
        sub.setObjectName("updatedLabel")
        layout.addWidget(sub)

        self._path_edit = QLineEdit(str(current_path))
        layout.addWidget(self._path_edit)

        btn_row = QHBoxLayout()
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        btn_row.addWidget(browse_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("primaryBtn")
        self._save_btn.clicked.connect(self._save)
        btn_row.addWidget(self._save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()

        layout.addLayout(btn_row)

    def _browse(self):
        chosen = QFileDialog.getExistingDirectory(
            self, "Select install directory", self._path_edit.text()
        )
        if chosen:
            self._path_edit.setText(chosen)

    def _save(self):
        new_path = Path(self._path_edit.text().strip())
        if not new_path.exists():
            reply = QMessageBox.question(
                self, "Create Directory?",
                f"Directory does not exist:\n{new_path}\n\nCreate it?",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._save_btn.setEnabled(False)
        self._save_btn.setText("Saving…")

        def _thread():
            new_path.mkdir(parents=True, exist_ok=True)
            set_setting(self._conn, "install_path", str(new_path))
            scan_and_sync(new_path, self._conn)
            self.path_saved.emit(new_path)
            self.accept()

        threading.Thread(target=_thread, daemon=True).start()
```

- [ ] **Step 2: Commit**

```bash
git add gui/settings_dialog.py
git commit -m "feat: rewrite SettingsDialog in PySide6"
```

---

## Task 10: gui/batch_results_dialog.py

**Files:**
- Rewrite: `gui/batch_results_dialog.py`

- [ ] **Step 1: Create gui/batch_results_dialog.py**

```python
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget,
)
from PySide6.QtCore import Signal

_ICONS = {"ok": "✓", "manual": "⚠", "error": "✗", "skipped": "—"}
_COLORS = {
    "ok":      "#52b788",
    "manual":  "#f4a261",
    "error":   "#e76f51",
    "skipped": "#888888",
}


class BatchResultsDialog(QDialog):
    closed = Signal()

    def __init__(self, results: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Download Results")
        self.resize(600, 420)
        self._build(results)

    def _build(self, results: list[dict]):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        ok_count = sum(1 for r in results if r["status"] == "ok")
        total = len(results)
        summary_color = "#52b788" if ok_count == total else "#f4a261"
        summary = QLabel(f"Batch Download — {ok_count} of {total} succeeded")
        summary.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {summary_color};"
        )
        layout.addWidget(summary)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            scroll.horizontalScrollBarPolicy().ScrollBarAlwaysOff
            if hasattr(scroll.horizontalScrollBarPolicy(), 'ScrollBarAlwaysOff')
            else 1  # Qt.ScrollBarAlwaysOff
        )
        from PySide6.QtCore import Qt
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(4, 4, 4, 4)
        inner_layout.setSpacing(4)

        for entry in results:
            song = entry["song"]
            status = entry["status"]
            msg = entry.get("message", "")
            icon = _ICONS.get(status, "?")
            color = _COLORS.get(status, "white")

            row = QHBoxLayout()
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(f"color: {color}; font-size: 13px; min-width: 16px;")
            icon_lbl.setFixedWidth(20)
            title_lbl = QLabel(song.get("title", "?"))
            title_lbl.setStyleSheet("font-size: 12px;")
            msg_lbl = QLabel(msg)
            msg_lbl.setStyleSheet("font-size: 11px; color: #888;")

            row.addWidget(icon_lbl)
            row.addWidget(title_lbl)
            row.addStretch()
            row.addWidget(msg_lbl)
            inner_layout.addLayout(row)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self._on_close)
        layout.addWidget(close_btn)

    def _on_close(self):
        self.closed.emit()
        self.accept()
```

- [ ] **Step 2: Commit**

```bash
git add gui/batch_results_dialog.py
git commit -m "feat: rewrite BatchResultsDialog in PySide6"
```

---

## Task 11: gui/main_window.py

**Files:**
- Rewrite: `gui/main_window.py`

- [ ] **Step 1: Rewrite gui/main_window.py**

```python
import sqlite3
from datetime import date
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QFrame, QLabel,
)
from PySide6.QtCore import Qt

from db import init_db, get_songs, get_song_by_id, get_setting, set_setting
from installer import scan_and_sync, uninstall, install_manual_files, DEFAULT_INSTALL_DIR

from gui.styles import APP_STYLE
from gui.filter_bar import FilterBar
from gui.song_table import SongTableModel, SongTableView
from gui.detail_panel import DetailPanel
from gui.status_bar import StatusBar
from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker
from gui.settings_dialog import SettingsDialog
from gui.batch_results_dialog import BatchResultsDialog


class FuserApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fuser Custom Song Manager")
        self.resize(1200, 800)
        self.setMinimumSize(800, 600)

        self.setStyleSheet(APP_STYLE)

        self.conn: sqlite3.Connection = init_db()
        path_str = get_setting(self.conn, "install_path")
        self._install_dir = Path(path_str) if path_str else DEFAULT_INSTALL_DIR
        self._batch_mode = False
        self._active_worker = None

        scan_and_sync(self._install_dir, self.conn)
        self._build_ui()
        self._refresh_table()
        self._check_dates_stale()

    # ── Layout ────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Filter bar (search + dropdowns)
        self.filter_bar = FilterBar()
        self.filter_bar.filters_changed.connect(self._on_filters_changed)
        self.filter_bar._refresh_btn.clicked.connect(self._start_refresh)
        self.filter_bar._settings_btn.clicked.connect(self._open_settings)
        self._batch_btn = QPushButton("☰ Batch Mode")
        self._batch_btn.clicked.connect(self._enter_batch_mode)
        self.filter_bar.add_to_toolbar(self._batch_btn)
        root.addWidget(self.filter_bar)

        # Batch bar (hidden until batch mode)
        self._batch_bar = self._build_batch_bar()
        self._batch_bar.hide()
        root.addWidget(self._batch_bar)

        # Splitter: table (left) + detail panel (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._model = SongTableModel()
        self.song_table = SongTableView()
        self.song_table.set_model(self._model)
        self.song_table.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        splitter.addWidget(self.song_table)

        self.detail_panel = DetailPanel()
        self.detail_panel.setObjectName("detailPanel")
        self.detail_panel.download_requested.connect(self._on_download)
        self.detail_panel.uninstall_requested.connect(self._on_uninstall)
        self.detail_panel.manual_install_requested.connect(self._on_manual_install)
        splitter.addWidget(self.detail_panel)

        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter)

        # Status bar
        self.status_bar = StatusBar()
        root.addWidget(self.status_bar)

    def _build_batch_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("batchbar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.clicked.connect(self.song_table.select_all)
        layout.addWidget(self._select_all_btn)

        self._deselect_all_btn = QPushButton("Deselect All")
        self._deselect_all_btn.clicked.connect(self.song_table.deselect_all)
        layout.addWidget(self._deselect_all_btn)

        layout.addStretch()

        self._download_btn = QPushButton("Download (0)")
        self._download_btn.setObjectName("downloadBtn")
        self._download_btn.setEnabled(False)
        self._download_btn.clicked.connect(self._on_batch_download)
        layout.addWidget(self._download_btn)

        self._exit_batch_btn = QPushButton("✕ Exit Batch")
        self._exit_batch_btn.clicked.connect(self._exit_batch_mode)
        layout.addWidget(self._exit_batch_btn)

        return bar

    # ── Data ──────────────────────────────────────────────────────────────

    def _refresh_table(self):
        filters = self.filter_bar.get_filters()
        rows = get_songs(self.conn, filters, limit=0)
        self._model.reset(rows)

    def _on_filters_changed(self, _filters: dict):
        self._refresh_table()

    def _check_dates_stale(self):
        null_dates = self.conn.execute(
            "SELECT COUNT(*) FROM songs WHERE submit_date IS NULL"
        ).fetchone()[0]
        if null_dates > 0:
            self.status_bar.set_message(
                f"{null_dates:,} songs have no date — click Refresh Sources to update."
            )

    # ── Selection ─────────────────────────────────────────────────────────

    def _on_selection_changed(self):
        if self._batch_mode:
            count = len(self.song_table.get_selected_songs())
            self._download_btn.setText(f"Download ({count})")
            self._download_btn.setEnabled(count > 0)
            return
        indexes = self.song_table.selectionModel().selectedRows()
        if not indexes:
            return
        song = self._model.get_row(indexes[0].row())
        self.detail_panel.show(song)

    # ── Batch mode ────────────────────────────────────────────────────────

    def _enter_batch_mode(self):
        self._batch_mode = True
        self._batch_btn.hide()
        self.detail_panel.hide()
        self._batch_bar.show()
        self.song_table.set_batch_mode(True)

    def _exit_batch_mode(self):
        self._batch_mode = False
        self.song_table.deselect_all()
        self.song_table.set_batch_mode(False)
        self._batch_bar.hide()
        self._batch_btn.show()
        self.detail_panel.show()
        self._download_btn.setText("Download (0)")
        self._download_btn.setEnabled(False)

    def _on_batch_download(self):
        songs = self.song_table.get_selected_songs()
        to_download = [s for s in songs if not s.get("pak_path")]
        already_installed = [s for s in songs if s.get("pak_path")]
        if not to_download:
            skipped = [
                {"song": s, "status": "skipped", "message": "Already installed"}
                for s in already_installed
            ]
            self._show_batch_results(skipped)
            return
        self._download_btn.setEnabled(False)
        self._download_btn.setText("Downloading…")
        worker = BatchDownloadWorker(to_download, self._install_dir, self.conn)
        skipped = [
            {"song": s, "status": "skipped", "message": "Already installed"}
            for s in already_installed
        ]
        worker.item_progress.connect(self.status_bar.set_message)
        worker.finished.connect(lambda results: self._on_batch_done(results + skipped))
        self._active_worker = worker
        worker.start()

    def _on_batch_done(self, results: list[dict]):
        self._refresh_table()
        self.status_bar.set_idle()
        self._show_batch_results(results)

    def _show_batch_results(self, results: list[dict]):
        dlg = BatchResultsDialog(results, parent=self)
        dlg.closed.connect(self._exit_batch_mode)
        dlg.exec()

    # ── Refresh sources ───────────────────────────────────────────────────

    def _start_refresh(self):
        self.filter_bar.set_refresh_enabled(False)
        worker = RefreshWorker(self.conn)
        worker.finished.connect(self._on_refresh_done)
        worker.error.connect(self.status_bar.set_error)
        worker.finished.connect(lambda: self.filter_bar.set_refresh_enabled(True))
        worker.error.connect(lambda _: self.filter_bar.set_refresh_enabled(True))
        self._active_worker = worker
        worker.start()

    def _on_refresh_done(self):
        self.filter_bar.set_updated_label(f"Updated {date.today().isoformat()}")
        self._refresh_table()

    # ── Download / install ────────────────────────────────────────────────

    def _on_download(self, song: dict):
        self.status_bar.start_download(song["title"])
        worker = DownloadWorker(song, self._install_dir, self.conn)
        worker.progress.connect(self.status_bar.set_progress)
        worker.done.connect(self._on_download_done)
        worker.manual.connect(self.detail_panel.show_manual_link)
        worker.manual.connect(lambda _: self.status_bar.set_idle())
        worker.error.connect(self.status_bar.set_error)
        self._active_worker = worker
        worker.start()

    def _on_download_done(self, title: str):
        self._refresh_table()
        self.status_bar.set_done(title)
        # Refresh the detail panel with updated song data
        indexes = self.song_table.selectionModel().selectedRows()
        if indexes:
            song = self._model.get_row(indexes[0].row())
            fresh = get_song_by_id(self.conn, song["id"])
            if fresh:
                self.detail_panel.show(fresh)

    def _on_uninstall(self, song: dict):
        uninstall(song["id"], self._install_dir, self.conn)
        self._refresh_table()
        fresh = get_song_by_id(self.conn, song["id"])
        if fresh:
            self.detail_panel.show(fresh)

    def _on_manual_install(self, song, pak_path, sig_path):
        install_manual_files(song["id"], song["artist"], pak_path, sig_path,
                             self._install_dir, self.conn)
        self._refresh_table()
        fresh = get_song_by_id(self.conn, song["id"])
        if fresh:
            self.detail_panel.show(fresh)

    # ── Settings ──────────────────────────────────────────────────────────

    def _open_settings(self):
        dlg = SettingsDialog(self._install_dir, self.conn, parent=self)
        dlg.path_saved.connect(self._on_path_saved)
        dlg.exec()

    def _on_path_saved(self, new_path: Path):
        self._install_dir = new_path
        self.status_bar.set_message(f"Install path: {new_path}")
        self._refresh_table()

    def mainloop(self):
        """Compatibility shim so app.py doesn't need changes."""
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        self.show()
        app.exec()
```

- [ ] **Step 2: Commit**

```bash
git add gui/main_window.py
git commit -m "feat: rewrite MainWindow in PySide6"
```

---

## Task 12: app.py + cleanup

**Files:**
- Modify: `app.py`
- Modify: `tests/test_gui_smoke.py`

- [ ] **Step 1: Update app.py**

```python
import sys
from PySide6.QtWidgets import QApplication
from gui.main_window import FuserApp


def main():
    app = QApplication(sys.argv)
    window = FuserApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update tests/test_gui_smoke.py**

```python
def test_gui_imports():
    from gui.main_window import FuserApp
    from gui.song_table import SongTableModel, SongTableView
    from gui.detail_panel import DetailPanel
    from gui.status_bar import StatusBar
    from gui.filter_bar import FilterBar
    from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker
    from gui.settings_dialog import SettingsDialog
    from gui.batch_results_dialog import BatchResultsDialog
    assert all([FuserApp, SongTableModel, SongTableView, DetailPanel, StatusBar,
                FilterBar, RefreshWorker, DownloadWorker, BatchDownloadWorker,
                SettingsDialog, BatchResultsDialog])
```

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v
```

Expected: all PASS. No customtkinter imports anywhere in tests.

- [ ] **Step 4: Launch the app and verify visually**

```bash
python app.py
```

Verify:
- Window opens, resizable
- Song table loads with install dots and quality badges
- Selecting a row populates the detail panel
- Filter dropdowns and search work
- Batch mode button shows batch bar, hides detail panel
- Select All / Deselect All / Download count updates

- [ ] **Step 5: Final commit**

```bash
git add app.py tests/test_gui_smoke.py
git commit -m "feat: complete PySide6 rewrite — remove customtkinter"
```
