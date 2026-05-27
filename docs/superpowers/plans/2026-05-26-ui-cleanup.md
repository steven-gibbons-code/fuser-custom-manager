# UI Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix layout scaling, restore gold/platinum/purple quality badge colours, make installed rows show a green background, and add a window icon.

**Architecture:** Four independent changes across two files plus a new `assets/` directory. No new abstractions beyond `_RowBgDelegate` in `song_table.py`. Changes are additive — no existing public interfaces change.

**Tech Stack:** PySide6, pytest-qt, Pillow (icon generation only, dev dependency)

---

### Task 1: Layout scaling fix

**Files:**
- Modify: `gui/main_window.py:85`
- Test: `tests/test_main_window_layout.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_main_window_layout.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock
from gui.main_window import FuserApp


def _make_app(qtbot):
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (0,)
    with patch("gui.main_window.init_db", return_value=mock_conn), \
         patch("gui.main_window.scan_and_sync"), \
         patch("gui.main_window.get_setting", return_value=None), \
         patch("gui.main_window.get_songs", return_value=[]):
        window = FuserApp()
    qtbot.addWidget(window)
    return window


def test_splitter_has_stretch_factor_1(qtbot):
    window = _make_app(qtbot)
    layout = window.centralWidget().layout()
    # Layout order: 0=filter_bar, 1=batch_bar, 2=splitter, 3=status_bar
    assert layout.stretch(2) == 1
```

- [ ] **Step 2: Run test to confirm it fails**

```
pytest tests/test_main_window_layout.py -v
```

Expected: FAIL — `assert 0 == 1`

- [ ] **Step 3: Apply the fix**

In `gui/main_window.py` line 85, change:

```python
        root.addWidget(splitter)
```

to:

```python
        root.addWidget(splitter, stretch=1)
```

- [ ] **Step 4: Run test to confirm it passes**

```
pytest tests/test_main_window_layout.py -v
```

Expected: PASS

- [ ] **Step 5: Run full suite to check for regressions**

```
pytest --tb=short -q
```

Expected: all tests pass (or same failures as before this task)

- [ ] **Step 6: Commit**

```bash
git add gui/main_window.py tests/test_main_window_layout.py
git commit -m "fix: give splitter stretch=1 so it fills available vertical space"
```

---

### Task 2: Quality badge colour palette

**Files:**
- Modify: `gui/song_table.py:15-20`
- Test: `tests/test_song_table_model.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_song_table_model.py`:

```python
from gui.song_table import _QUALITY_COLORS


def test_quality_color_complete():
    bg, fg = _QUALITY_COLORS["Complete"]
    assert bg == "#2e2000"
    assert fg == "#d4a017"


def test_quality_color_definitive():
    bg, fg = _QUALITY_COLORS["Definitive"]
    assert bg == "#252530"
    assert fg == "#a0a8b8"


def test_quality_color_official():
    bg, fg = _QUALITY_COLORS["Official"]
    assert bg == "#1a1535"
    assert fg == "#8b7de8"


def test_quality_color_other_unchanged():
    bg, fg = _QUALITY_COLORS["Other"]
    assert bg == "#2a2a2a"
    assert fg == "#888888"
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_song_table_model.py::test_quality_color_complete tests/test_song_table_model.py::test_quality_color_definitive tests/test_song_table_model.py::test_quality_color_official -v
```

Expected: FAIL — assertion errors on the old colour values

- [ ] **Step 3: Replace `_QUALITY_COLORS`**

In `gui/song_table.py`, replace lines 15–20:

```python
_QUALITY_COLORS = {
    "Official":   ("#1d3557", "#74b3f0"),
    "Definitive": ("#2d2a00", "#fde68a"),
    "Complete":   ("#1a2e1a", "#86efac"),
    "Other":      ("#2a2a2a", "#888888"),
}
```

with:

```python
_QUALITY_COLORS = {
    "Official":   ("#1a1535", "#8b7de8"),
    "Definitive": ("#252530", "#a0a8b8"),
    "Complete":   ("#2e2000", "#d4a017"),
    "Other":      ("#2a2a2a", "#888888"),
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/test_song_table_model.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add gui/song_table.py tests/test_song_table_model.py
git commit -m "fix: restore gold/silver/purple quality badge palette"
```

---

### Task 3: Installed row green background

**Files:**
- Modify: `gui/song_table.py:68` (BackgroundRole colour)
- Modify: `gui/song_table.py:83-86` (InstallDelegate else branch)
- Modify: `gui/song_table.py` (add `_RowBgDelegate` class before `SongTableView`)
- Modify: `gui/song_table.py` (update `SongTableView.set_model` to assign `_RowBgDelegate`)
- Test: `tests/test_song_table_model.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_song_table_model.py`:

```python
def test_background_role_installed_row_is_dark_green(qtbot):
    model = SongTableModel()
    model.reset([{
        "id": 1, "title": "T", "artist": "A", "bpm": 120,
        "quality": "Complete", "source": "s", "pak_path": "/foo.pak",
    }])
    idx = model.index(0, COL_TITLE)
    brush = model.data(idx, Qt.ItemDataRole.BackgroundRole)
    assert brush is not None
    assert brush.color().name() == "#152215"


def test_background_role_uninstalled_row_is_none(qtbot):
    model = SongTableModel()
    model.reset([{
        "id": 2, "title": "T", "artist": "A", "bpm": 120,
        "quality": "Complete", "source": "s", "pak_path": None,
    }])
    idx = model.index(0, COL_TITLE)
    brush = model.data(idx, Qt.ItemDataRole.BackgroundRole)
    assert brush is None


def test_background_role_not_set_for_installed_column(qtbot):
    model = SongTableModel()
    model.reset([{
        "id": 1, "title": "T", "artist": "A", "bpm": 120,
        "quality": "Complete", "source": "s", "pak_path": "/foo.pak",
    }])
    idx = model.index(0, COL_INSTALLED)
    brush = model.data(idx, Qt.ItemDataRole.BackgroundRole)
    assert brush is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_song_table_model.py::test_background_role_installed_row_is_dark_green tests/test_song_table_model.py::test_background_role_uninstalled_row_is_none tests/test_song_table_model.py::test_background_role_not_set_for_installed_column -v
```

Expected: first test fails (`#1a2e1a` ≠ `#152215`), other two pass (they already work)

- [ ] **Step 3: Update `BackgroundRole` colour in the model**

In `gui/song_table.py`, in `SongTableModel.data()`, change the `BackgroundRole` block (around line 66):

```python
        if role == Qt.ItemDataRole.BackgroundRole:
            if row.get("pak_path") and col != COL_INSTALLED:
                return QBrush(QColor("#152215"))
```

- [ ] **Step 4: Run BackgroundRole tests to confirm they pass**

```
pytest tests/test_song_table_model.py::test_background_role_installed_row_is_dark_green tests/test_song_table_model.py::test_background_role_uninstalled_row_is_none tests/test_song_table_model.py::test_background_role_not_set_for_installed_column -v
```

Expected: all three pass

- [ ] **Step 5: Fix `InstallDelegate.paint()` to apply `BackgroundRole`**

In `gui/song_table.py`, replace the `InstallDelegate.paint()` method:

```python
class InstallDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index: QModelIndex):
        song = index.data(Qt.ItemDataRole.UserRole)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#1e3a5f"))
        else:
            bg = index.data(Qt.ItemDataRole.BackgroundRole)
            painter.fillRect(option.rect, bg.color() if bg else QColor("#1c1c1c"))
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
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
        painter.restore()
```

- [ ] **Step 6: Add `_RowBgDelegate` before `SongTableView`**

Insert this class in `gui/song_table.py` immediately before `class SongTableView`:

```python
class _RowBgDelegate(QStyledItemDelegate):
    """Applies model BackgroundRole to columns using Qt's default text rendering.

    Without this, QSS alternate-background-color overrides BackgroundRole
    for cells that don't have a custom delegate.
    """
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        bg = index.data(Qt.ItemDataRole.BackgroundRole)
        if bg:
            option.backgroundBrush = bg
```

- [ ] **Step 7: Assign `_RowBgDelegate` in `SongTableView.set_model`**

In `gui/song_table.py`, update `SongTableView.set_model()` to add four delegate assignments after the existing two:

```python
    def set_model(self, model: SongTableModel):
        self.setModel(model)
        self.setItemDelegateForColumn(COL_INSTALLED, InstallDelegate(self))
        self.setItemDelegateForColumn(COL_QUALITY, QualityDelegate(self))
        self.setItemDelegateForColumn(COL_TITLE, _RowBgDelegate(self))
        self.setItemDelegateForColumn(COL_ARTIST, _RowBgDelegate(self))
        self.setItemDelegateForColumn(COL_BPM, _RowBgDelegate(self))
        self.setItemDelegateForColumn(COL_SOURCE, _RowBgDelegate(self))
        self.setColumnWidth(COL_INSTALLED, 28)
        self.setColumnWidth(COL_BPM, 60)
        self.setColumnWidth(COL_QUALITY, 100)
        self.setColumnWidth(COL_SOURCE, 110)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        self.setColumnWidth(COL_ARTIST, 160)
```

- [ ] **Step 8: Run full suite**

```
pytest --tb=short -q
```

Expected: all tests pass

- [ ] **Step 9: Commit**

```bash
git add gui/song_table.py tests/test_song_table_model.py
git commit -m "fix: restore green row background for installed songs"
```

---

### Task 4: Window icon

**Files:**
- Create: `assets/generate_icon.py`
- Create: `assets/icon.ico` (generated, then committed)
- Modify: `gui/main_window.py:31` (after `self.setStyleSheet`)
- Test: `tests/test_icon.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_icon.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_icon_file_exists():
    icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"
    assert icon_path.exists(), "assets/icon.ico not found — run: python assets/generate_icon.py"


def test_icon_is_valid_ico():
    from PIL import Image
    icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"
    if not icon_path.exists():
        import pytest
        pytest.skip("icon not generated yet")
    img = Image.open(icon_path)
    assert img.format == "ICO"
```

- [ ] **Step 2: Run test to confirm it fails**

```
pytest tests/test_icon.py -v
```

Expected: FAIL — `assets/icon.ico not found`

- [ ] **Step 3: Create `assets/generate_icon.py`**

Create the directory first, then create `assets/generate_icon.py`:

```python
"""Generate assets/icon.ico — run once: python assets/generate_icon.py"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

SIZES = [16, 32, 48]
OUT = Path(__file__).parent / "icon.ico"

BG_DARK   = (28, 28, 28, 255)
BLUE      = (37, 99, 235, 255)
WHITE     = (220, 220, 220, 255)


def _draw_frame(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    radius = max(2, size // 6)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG_DARK)

    # Music note: filled oval (note head) + stem + flag
    s = size / 48.0  # scale factor relative to 48px base

    # Note head
    hx, hy = int(10 * s), int(28 * s)
    hw, hh = max(2, int(12 * s)), max(2, int(10 * s))
    d.ellipse([hx, hy, hx + hw, hy + hh], fill=BLUE)

    # Stem
    sx = hx + hw - max(1, int(2 * s))
    d.rectangle([sx, int(12 * s), sx + max(1, int(3 * s)), hy + hh // 2], fill=BLUE)

    # Flag (two small arcs approximated as lines)
    fx = sx + max(1, int(3 * s))
    for i in range(2):
        y_start = int((12 + i * 6) * s)
        y_end = int((18 + i * 6) * s)
        d.line([fx, y_start, fx + int(8 * s), y_start + int(4 * s),
                fx + int(6 * s), y_end], fill=BLUE, width=max(1, int(2 * s)))

    return img


def main():
    frames = [_draw_frame(sz) for sz in SIZES]
    frames[0].save(OUT, format="ICO", sizes=[(sz, sz) for sz in SIZES],
                   append_images=frames[1:])
    print(f"Written: {OUT}  ({', '.join(str(s)+'px' for s in SIZES)})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Install Pillow (dev only) and run the generator**

```
pip install pillow
python assets/generate_icon.py
```

Expected output: `Written: assets/icon.ico  (16px, 32px, 48px)`

- [ ] **Step 5: Run test to confirm it passes**

```
pytest tests/test_icon.py -v
```

Expected: PASS

- [ ] **Step 6: Wire the icon into `FuserApp.__init__`**

In `gui/main_window.py`, after `self.setStyleSheet(APP_STYLE)` (line 31), add:

```python
        from PySide6.QtGui import QIcon
        _icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"
        if _icon_path.exists():
            self.setWindowIcon(QIcon(str(_icon_path)))
```

The `Path(__file__)` approach is robust regardless of the working directory the app is launched from.

- [ ] **Step 7: Run full suite**

```
pytest --tb=short -q
```

Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add assets/generate_icon.py assets/icon.ico tests/test_icon.py gui/main_window.py
git commit -m "feat: add window icon generated with Pillow"
```

---

## Verification

After all four tasks, run the app and confirm:
- Song list fills the window height and grows/shrinks with resize
- Quality badges show ochre (Complete), silver (Definitive), purple (Official)
- Installed songs have a visible dark-green row background across all columns
- Window icon appears in the title bar and taskbar

```
python app.py
```
