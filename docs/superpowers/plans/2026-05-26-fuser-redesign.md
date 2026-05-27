# Fuser Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the muted dark QSS with Fuser's game aesthetic — deep purple stage backdrop, pink→orange gradient, Sora typeface, 64px card rows with album-art thumbnails, and pill controls.

**Architecture:** Three independent layers committed separately. Layer 1 (tokens + QSS + font + resources) is a pure visual refresh with no code-path changes. Layer 2 (SongRowDelegate + single-column model + FuserLabel) replaces the per-column delegate architecture. Layer 3 (StageBackdrop + main_window wiring) adds the backdrop widget and connects FuserLabel to the topbar.

**Tech Stack:** PySide6 6.x, pytest-qt, pyside6-rcc (already installed)

---

## File Map

| File | Layer | Action |
|---|---|---|
| `gui/tokens.py` | 1 | Create — design token dict + QColor helper |
| `gui/styles.py` | 1 | Replace entirely — QSS template using tokens |
| `assets/fonts/Sora-VariableFont_wght.ttf` | 1 | Download from Google Fonts, commit |
| `assets/icons/instruments/*.png` (8 files) | 1 | Copy from design package, commit |
| `assets/icons/utility/*.png` (8 files) | 1 | Copy from design package, commit |
| `assets.qrc` | 1 | Create — Qt resource file at project root |
| `assets_rc.py` | 1 | Generate via pyside6-rcc, commit |
| `app.py` | 1 | Update boot sequence (font, cache, stylesheet) |
| `gui/main_window.py` | 1 | Remove `setStyleSheet` call + `APP_STYLE` import |
| `gui/song_delegate.py` | 2 | Create — SongRowDelegate full-row card painter |
| `gui/song_table.py` | 2 | Collapse model to 1 column, rewire view delegate |
| `gui/widgets/__init__.py` | 2 | Create — empty package file |
| `gui/widgets/fuser_label.py` | 2 | Create — gradient FUSER logotype widget |
| `tests/test_song_table_model.py` | 2 | Remove obsolete column/colour tests, update columnCount |
| `gui/widgets/stage_backdrop.py` | 3 | Create — radial gradient backdrop widget |
| `gui/main_window.py` | 3 | Add StageBackdrop + resizeEvent + FuserLabel in topbar |
| `tests/test_gui_smoke.py` | 3 | Add FuserLabel + StageBackdrop presence assertions |

---

## Layer 1 — Foundation

### Task 1: Design tokens

**Files:**
- Create: `gui/tokens.py`

- [ ] **Step 1: Create `gui/tokens.py`**

```python
"""Design tokens — single source of truth for all colours and gradients.

All QSS templates and paint code import from here. Never hardcode hex values
elsewhere — add a token if one is missing.
"""
from PySide6.QtGui import QColor

TOKENS = {
    # ── Surfaces ────────────────────────────────────────────────
    "surface_0":          "#0a0420",
    "surface_1":          "#150629",
    "surface_2":          "#1a0b32",
    "surface_3":          "#20133a",
    "surface_4":          "#2a1845",
    "surface_5":          "#3a205a",
    "surface_6":          "#4a2a6f",

    # ── FUSER gradient stops ───────────────────────────────────
    "accent_pink":        "#ff5e9e",
    "accent_orange":      "#ff8a5b",
    "accent_purple":      "#c14fff",
    "accent_yellow":      "#ffd166",

    # ── Solid accents ──────────────────────────────────────────
    "selection_purple":   "#5b2d8a",
    "success":            "#4ad15c",
    "warning":            "#ffb84d",
    "danger":             "#ef5350",

    # ── Stem colours ──────────────────────────────────────────
    "stem_dj":            "#4fc3f7",
    "stem_bass":          "#66bb6a",
    "stem_synth":         "#ffd54f",
    "stem_vocals":        "#ef5350",

    # ── Text ───────────────────────────────────────────────────
    "fg_white":           "#ffffff",
    "fg_soft":            "#ece4ff",
    "fg_muted":           "#b3a5d4",
    "fg_tertiary":        "#7c6aa3",
    "fg_disabled":        "#4a3a6e",

    # ── Tier pills (rgba strings for QSS; use _rgba() in paint code) ──
    "tier_official_bg":   "rgba(193, 79, 255, 0.18)",
    "tier_official_fg":   "#d29aff",
    "tier_definitive_bg": "rgba(255, 94, 158, 0.20)",
    "tier_definitive_fg": "#ff9bc2",
    "tier_complete_bg":   "rgba(79, 195, 247, 0.18)",
    "tier_complete_fg":   "#82d6fa",
    "tier_other_bg":      "rgba(124, 106, 163, 0.18)",
    "tier_other_fg":      "#b3a5d4",
}

# QSS-syntax gradients (qlineargradient / qradialgradient, not CSS syntax)
GRADIENTS = {
    "fuser":      "qlineargradient(x1:0, y1:0.5, x2:1, y2:0.5, "
                  "stop:0 #ff5e9e, stop:1 #ff8a5b)",
    "fuser_logo": "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                  "stop:0 #c14fff, stop:0.3 #ff5e9e, "
                  "stop:0.65 #ff8a5b, stop:1 #ffd166)",
    "stage":      "qradialgradient(cx:0.5, cy:1.1, radius:1.2, "
                  "fx:0.5, fy:1.1, stop:0 #ff5e9e, stop:0.22 #6b2d7a, "
                  "stop:0.5 #2a0d4a, stop:1 #0a0420)",
}


def C(name: str, alpha: float | None = None) -> QColor:
    """Return a QColor for a hex token. Do not use with rgba() tokens."""
    c = QColor(TOKENS[name])
    if alpha is not None:
        c.setAlphaF(alpha)
    return c
```

- [ ] **Step 2: Verify import works**

```
python -c "from gui.tokens import TOKENS, GRADIENTS, C; print(C('accent_pink').name())"
```

Expected output: `#ff5e9e`

- [ ] **Step 3: Commit**

```bash
git add gui/tokens.py
git commit -m "feat: add design token dict and QColor helper (Layer 1)"
```

---

### Task 2: Replace QSS

**Files:**
- Modify: `gui/styles.py` (full replacement)
- Modify: `gui/main_window.py:15,32` (remove import + setStyleSheet)

- [ ] **Step 1: Replace `gui/styles.py` entirely**

Delete all existing content and write:

```python
from gui.tokens import TOKENS, GRADIENTS

APP_STYLE = """
QMainWindow, QDialog {{
    background: {surface_2};
    color: {fg_soft};
    font-family: "Sora";
    font-size: 14px;
}}

QWidget {{
    background: transparent;
    color: {fg_soft};
    font-family: "Sora";
    font-size: 14px;
}}

/* ── Toolbar / filter frames ── */
QFrame#toolbar, QFrame#filterbar, QFrame#batchbar {{
    background: rgba(10, 4, 32, 0.5);
    border-bottom: 1px solid rgba(255,255,255,0.04);
}}

/* ── Inputs ── */
QLineEdit {{
    background: {surface_1};
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 0 18px;
    color: {fg_white};
    min-height: 34px;
    font-size: 13px;
}}
QLineEdit:focus {{
    border-color: {accent_pink};
}}

/* ── Dropdowns ── */
QComboBox {{
    background: {surface_2};
    color: {fg_soft};
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 18px;
    padding: 6px 28px 6px 14px;
    font-size: 13px;
    min-height: 28px;
}}
QComboBox:focus {{
    border-color: {accent_pink};
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox::down-arrow {{
    width: 8px;
    height: 8px;
    border: 2px solid {fg_tertiary};
    border-top: none;
    border-right: none;
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background: {surface_2};
    border: 1px solid rgba(255,255,255,0.08);
    color: {fg_soft};
    selection-background-color: {selection_purple};
}}

/* ── Buttons ── */
QPushButton {{
    background: {surface_2};
    color: {fg_soft};
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 22px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    min-height: 24px;
}}
QPushButton:hover {{
    background: {surface_3};
    border-color: rgba(255,255,255,0.18);
}}
QPushButton:pressed {{
    background: {surface_1};
}}
QPushButton:disabled {{
    color: {fg_disabled};
    border-color: rgba(255,255,255,0.04);
}}

QPushButton#primaryBtn {{
    background: {fuser};
    color: white;
    border: 1px solid rgba(255,255,255,0.06);
}}
QPushButton#primaryBtn:hover {{
    background: {fuser};
    border-color: rgba(255,255,255,0.2);
}}
QPushButton#primaryBtn:disabled {{
    background: {surface_1};
    color: {fg_disabled};
}}

QPushButton#downloadBtn {{
    background: transparent;
    color: {success};
    border: 1px solid rgba(74,209,92,0.4);
}}
QPushButton#downloadBtn:hover {{
    background: rgba(74,209,92,0.1);
}}
QPushButton#downloadBtn:disabled {{
    color: {fg_disabled};
    border-color: rgba(255,255,255,0.04);
}}

QPushButton#dangerBtn {{
    background: transparent;
    color: {danger};
    border: 1px solid rgba(239,83,80,0.4);
}}
QPushButton#dangerBtn:hover {{
    background: rgba(239,83,80,0.1);
}}
QPushButton#dangerBtn:disabled {{
    color: {fg_disabled};
    border-color: rgba(255,255,255,0.04);
}}

QPushButton#manualBtn {{
    background: transparent;
    color: {warning};
    border: 1px solid rgba(255,184,77,0.4);
}}
QPushButton#manualBtn:hover {{
    background: rgba(255,184,77,0.1);
}}

/* ── Table ── */
QTableView {{
    background: transparent;
    selection-background-color: transparent;
    selection-color: {fg_white};
    border: none;
    gridline-color: transparent;
    outline: 0;
}}
QTableView::item {{
    padding: 0;
    border: none;
}}
QTableView::item:selected {{
    background: transparent;
    color: {fg_white};
}}

QHeaderView::section {{
    background: transparent;
    color: {fg_tertiary};
    border: 0;
    padding: 8px 14px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}}

/* ── Scrollbars ── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,0.1);
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(255,255,255,0.2);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: rgba(255,255,255,0.1);
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Status bar ── */
QStatusBar {{
    background: rgba(10,4,32,0.6);
    color: {fg_soft};
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 22px;
    font-size: 13px;
    min-height: 36px;
    margin: 4px 8px;
}}
QStatusBar QLabel {{
    background: transparent;
    padding: 0 4px;
}}

QProgressBar {{
    background: rgba(255,255,255,0.06);
    border: none;
    border-radius: 3px;
    max-height: 4px;
    text-visible: false;
}}
QProgressBar::chunk {{
    background: {fuser};
    border-radius: 3px;
}}

/* ── Labels ── */
QLabel#sectionTitle {{
    color: {fg_tertiary};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
}}
QLabel#updatedLabel {{
    color: {fg_tertiary};
    font-size: 11px;
}}
QLabel#manualLabel {{
    color: {warning};
}}
QLabel#errorLabel {{
    color: {danger};
}}
QLabel#successLabel {{
    color: {success};
}}

/* ── Splitter ── */
QSplitter::handle {{
    background: rgba(255,255,255,0.04);
    width: 1px;
}}

/* ── Detail panel ── */
QFrame#detailPanel {{
    background: {surface_2};
    border-radius: 20px;
    border: 1px solid rgba(255,255,255,0.05);
}}
""".format(**TOKENS, **GRADIENTS)
```

- [ ] **Step 2: Remove `APP_STYLE` import and `setStyleSheet` from `gui/main_window.py`**

In `gui/main_window.py`, remove line 15:
```python
from gui.styles import APP_STYLE
```

And remove line 32:
```python
        self.setStyleSheet(APP_STYLE)
```

- [ ] **Step 3: Run the smoke test to confirm app still imports**

```
pytest tests/test_gui_smoke.py -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add gui/styles.py gui/main_window.py
git commit -m "feat: replace QSS with Fuser-themed purple/gradient palette (Layer 1)"
```

---

### Task 3: Icons, font, and Qt resources

**Files:**
- Create: `assets/icons/instruments/` (8 PNGs)
- Create: `assets/icons/utility/` (8 PNGs)
- Create: `assets/fonts/Sora-VariableFont_wght.ttf`
- Create: `assets.qrc`
- Create: `assets_rc.py` (generated)

- [ ] **Step 1: Copy icon PNGs from the extracted design package**

```bash
DESIGN="/tmp/design_extracted/fuser-custom-manager-design-system/project/assets/icons"
mkdir -p assets/icons/instruments assets/icons/utility
cp "$DESIGN"/instruments/*.png assets/icons/instruments/
cp "$DESIGN"/utility/*.png     assets/icons/utility/
```

Confirm 16 files:
```bash
find assets/icons -type f | wc -l
```
Expected: `16`

- [ ] **Step 2: Download Sora variable font**

```bash
mkdir -p assets/fonts
curl -L "https://github.com/google/fonts/raw/main/ofl/sora/Sora%5Bwght%5D.ttf" \
     -o assets/fonts/Sora-VariableFont_wght.ttf
```

Confirm file size > 100 KB:
```bash
ls -lh assets/fonts/Sora-VariableFont_wght.ttf
```

- [ ] **Step 3: Create `assets.qrc` at the project root**

```xml
<RCC>
  <qresource prefix="/">
    <file alias="fonts/Sora-VariableFont_wght.ttf">assets/fonts/Sora-VariableFont_wght.ttf</file>
    <file alias="icons/instruments/drums.png">assets/icons/instruments/drums.png</file>
    <file alias="icons/instruments/guitar.png">assets/icons/instruments/guitar.png</file>
    <file alias="icons/instruments/horns.png">assets/icons/instruments/horns.png</file>
    <file alias="icons/instruments/piano.png">assets/icons/instruments/piano.png</file>
    <file alias="icons/instruments/strings.png">assets/icons/instruments/strings.png</file>
    <file alias="icons/instruments/synth-piano.png">assets/icons/instruments/synth-piano.png</file>
    <file alias="icons/instruments/synth.png">assets/icons/instruments/synth.png</file>
    <file alias="icons/instruments/vocals.png">assets/icons/instruments/vocals.png</file>
    <file alias="icons/utility/achievements.png">assets/icons/utility/achievements.png</file>
    <file alias="icons/utility/display.png">assets/icons/utility/display.png</file>
    <file alias="icons/utility/notice.png">assets/icons/utility/notice.png</file>
    <file alias="icons/utility/parameters.png">assets/icons/utility/parameters.png</file>
    <file alias="icons/utility/riser.png">assets/icons/utility/riser.png</file>
    <file alias="icons/utility/settings.png">assets/icons/utility/settings.png</file>
    <file alias="icons/utility/store.png">assets/icons/utility/store.png</file>
    <file alias="icons/utility/volume.png">assets/icons/utility/volume.png</file>
  </qresource>
</RCC>
```

- [ ] **Step 4: Generate `assets_rc.py`**

```bash
pyside6-rcc assets.qrc -o assets_rc.py
```

Confirm file was created:
```bash
head -3 assets_rc.py
```

Expected: starts with `# Resource object code` or similar pyside6-rcc header.

- [ ] **Step 5: Commit**

```bash
git add assets/icons/ assets/fonts/ assets.qrc assets_rc.py
git commit -m "feat: add Sora font, Fuser icon PNGs, and Qt resource file (Layer 1)"
```

---

### Task 4: Boot sequence

**Files:**
- Modify: `app.py` (full replacement)

- [ ] **Step 1: Verify `assets_rc` can be imported**

```bash
python -c "import assets_rc; print('ok')"
```

Expected: `ok`

- [ ] **Step 2: Replace `app.py`**

```python
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QFont, QPixmapCache
from PySide6.QtWidgets import QApplication

import assets_rc  # noqa: F401 — registers Qt resources (font + icons)

QApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)

app = QApplication(sys.argv)

# Sora must be registered before any widget (including QSS) is created
QFontDatabase.addApplicationFont(":/fonts/Sora-VariableFont_wght.ttf")
app.setFont(QFont("Sora", 10))

# Pre-size the album-art gradient pixmap cache
QPixmapCache.setCacheLimit(20_000)  # KB

from gui.styles import APP_STYLE  # noqa: E402 — must come after QApplication
app.setStyleSheet(APP_STYLE)

from gui.main_window import FuserApp  # noqa: E402
window = FuserApp()
window.show()
sys.exit(app.exec())
```

- [ ] **Step 3: Verify font is applied**

```bash
python -c "
import sys
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
import assets_rc
app = QApplication(sys.argv)
QFontDatabase.addApplicationFont(':/fonts/Sora-VariableFont_wght.ttf')
app.setFont(QFont('Sora', 10))
print(app.font().family())
"
```

Expected output: `Sora`

- [ ] **Step 4: Run full test suite**

```
pytest --tb=short -q
```

Expected: all tests pass (or same pre-existing failures as before this task).

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: update boot sequence — register Sora, set stylesheet in app.py (Layer 1)"
```

---

## Layer 2 — Card rows

### Task 5: SongRowDelegate

**Files:**
- Create: `gui/song_delegate.py`

- [ ] **Step 1: Create `gui/song_delegate.py`**

```python
import re
from PySide6.QtCore import Qt, QRect, QRectF, QSize, QPointF, QModelIndex
from PySide6.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QLinearGradient,
    QPainterPath, QBrush, QPen, QPixmap, QPixmapCache,
)
from PySide6.QtWidgets import QStyledItemDelegate, QStyle

from gui.tokens import TOKENS, C

ROW_HEIGHT = 64
ART_SIZE   = 48
ART_RADIUS = 10
ROW_RADIUS = 14

_PALETTES = [
    ("#5b2d8a", "#ff5e9e"),
    ("#ff5e9e", "#ff8a5b"),
    ("#4fc3f7", "#5b2d8a"),
    ("#66bb6a", "#ffd54f"),
    ("#ef5350", "#ff8a5b"),
    ("#c14fff", "#ff5e9e"),
    ("#ff8a5b", "#ffd54f"),
    ("#4fc3f7", "#66bb6a"),
]


def _rgba(token_str: str) -> QColor:
    """Parse 'rgba(r, g, b, a)' token string into QColor."""
    m = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", token_str)
    if not m:
        return QColor(token_str)
    r, g, b, a = m.groups()
    return QColor(int(r), int(g), int(b), int(float(a) * 255))


def _art_pixmap(song_id: int, size: int = ART_SIZE) -> QPixmap:
    """Return a cached gradient album-art square for the given song id."""
    key = f"art_{song_id}_{size}"
    pm = QPixmap()
    if not QPixmapCache.find(key, pm):
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        a, b = _PALETTES[abs(song_id) % len(_PALETTES)]
        g = QLinearGradient(0, 0, size, size)
        g.setColorAt(0, QColor(a))
        g.setColorAt(1, QColor(b))
        path = QPainterPath()
        path.addRoundedRect(0, 0, size, size, ART_RADIUS, ART_RADIUS)
        p.fillPath(path, QBrush(g))
        p.setPen(QPen(QColor(255, 255, 255, 20), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.end()
        QPixmapCache.insert(key, pm)
    return pm


class SongRowDelegate(QStyledItemDelegate):
    def sizeHint(self, opt, idx) -> QSize:
        return QSize(opt.rect.width(), ROW_HEIGHT)

    def paint(self, p: QPainter, opt, idx: QModelIndex):
        song = idx.data(Qt.ItemDataRole.UserRole)
        if not song:
            return

        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        hovered  = bool(opt.state & QStyle.StateFlag.State_MouseOver)

        # Card inset: 3px top/bottom creates a 6px gap between cards
        card = QRectF(opt.rect).adjusted(0, 3, 0, -3)

        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # ── Card background ─────────────────────────────────────
        if selected:
            bg = C("surface_6")
        elif hovered:
            bg = C("surface_5")
        else:
            bg = C("surface_4")

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        card_path = QPainterPath()
        card_path.addRoundedRect(card, ROW_RADIUS, ROW_RADIUS)
        p.drawPath(card_path)

        # Inner top-edge highlight
        p.setPen(QPen(QColor(255, 255, 255, 12), 1))
        p.drawLine(
            QPointF(card.left() + ROW_RADIUS, card.top() + 0.5),
            QPointF(card.right() - ROW_RADIUS, card.top() + 0.5),
        )

        # Pink rim on selected
        if selected:
            p.setPen(QPen(C("accent_pink", 0.5), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(card_path)

        # ── Install dot ─────────────────────────────────────────
        installed = bool(song.get("pak_path"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(C("success") if installed else QColor(255, 255, 255, 26))
        dot_cx = card.left() + 19
        dot_cy = card.center().y()
        p.drawEllipse(QPointF(dot_cx, dot_cy), 5, 5)

        # ── Album art ───────────────────────────────────────────
        art_x = int(card.left() + 36)
        art_y = int(card.center().y() - ART_SIZE / 2)
        p.drawPixmap(art_x, art_y, _art_pixmap(song["id"]))

        # ── Text ────────────────────────────────────────────────
        text_x    = art_x + ART_SIZE + 14
        pill_w    = 100
        bpm_w     = 70
        text_right = card.right() - pill_w - bpm_w - 28

        title_font = QFont("Sora", 11)
        title_font.setWeight(QFont.Weight.DemiBold)
        p.setFont(title_font)
        p.setPen(C("fg_white"))
        fm = QFontMetrics(title_font)
        title = fm.elidedText(
            song.get("title", "—"), Qt.TextElideMode.ElideRight,
            int(text_right - text_x),
        )
        p.drawText(int(text_x), int(card.top() + 24), title)

        sub_font = QFont("Sora", 9)
        sub_font.setWeight(QFont.Weight.Medium)
        p.setFont(sub_font)
        p.setPen(C("fg_muted"))
        bits = [song.get("artist", ""), song.get("source", ""), song.get("key", "")]
        sub = " · ".join(b for b in bits if b)
        fm = QFontMetrics(sub_font)
        sub = fm.elidedText(sub, Qt.TextElideMode.ElideRight, int(text_right - text_x))
        p.drawText(int(text_x), int(card.top() + 44), sub)

        # ── Quality pill ────────────────────────────────────────
        pill_x = card.right() - pill_w - bpm_w - 14
        pill_y = card.center().y() - 11
        self._draw_pill(p, pill_x, pill_y, pill_w, 22,
                        song.get("quality", "Other"), installed)

        # ── BPM block ───────────────────────────────────────────
        bpm_x = card.right() - bpm_w - 4
        big = QFont("Sora", 13)
        big.setWeight(QFont.Weight.DemiBold)
        p.setFont(big)
        p.setPen(C("fg_white"))
        p.drawText(int(bpm_x), int(card.top() + 28), str(song.get("bpm") or "—"))
        cap = QFont("Sora", 8)
        cap.setWeight(QFont.Weight.Medium)
        p.setFont(cap)
        p.setPen(C("fg_tertiary"))
        p.drawText(int(bpm_x), int(card.top() + 44), "BPM")

        p.restore()

    def _draw_pill(self, p: QPainter, x, y, w, h, quality: str, installed: bool):
        if installed:
            bg = _rgba("rgba(74, 209, 92, 0.18)")
            fg = QColor("#7be089")
            label = f"✓ {quality}"
        else:
            bg_key, fg_key = {
                "Official":   ("tier_official_bg",   "tier_official_fg"),
                "Definitive": ("tier_definitive_bg", "tier_definitive_fg"),
                "Complete":   ("tier_complete_bg",   "tier_complete_fg"),
            }.get(quality, ("tier_other_bg", "tier_other_fg"))
            bg = _rgba(TOKENS[bg_key])
            fg = QColor(TOKENS[fg_key])
            label = quality

        path = QPainterPath()
        path.addRoundedRect(x, y, w, h, h / 2, h / 2)
        p.fillPath(path, bg)

        f = QFont("Sora", 8)
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(fg)
        p.drawText(
            QRect(int(x), int(y), int(w), int(h)),
            Qt.AlignmentFlag.AlignCenter,
            label,
        )
```

- [ ] **Step 2: Verify it imports cleanly**

```bash
python -c "from gui.song_delegate import SongRowDelegate, ROW_HEIGHT; print(ROW_HEIGHT)"
```

Expected: `64`

- [ ] **Step 3: Commit**

```bash
git add gui/song_delegate.py
git commit -m "feat: add SongRowDelegate full-row card painter (Layer 2)"
```

---

### Task 6: Collapse model to single column and rewire view

**Files:**
- Modify: `gui/song_table.py`

- [ ] **Step 1: Write failing tests**

In `tests/test_song_table_model.py`, find and update `test_column_count`:

```python
def test_column_count(qtbot):
    model = SongTableModel()
    assert model.columnCount() == 1
```

Run to confirm it fails:

```
pytest tests/test_song_table_model.py::test_column_count -v
```

Expected: FAIL (`assert 7 == 1`)

- [ ] **Step 2: Replace `gui/song_table.py` entirely**

```python
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QSize
from PySide6.QtWidgets import (
    QTableView, QStyledItemDelegate, QAbstractItemView,
)

# Column constants kept for get_songs() filter compatibility and tests
COL_INSTALLED = 0
COL_QUALITY   = 1
COL_TITLE     = 2
COL_ARTIST    = 3
COL_KEY       = 4
COL_BPM       = 5
COL_SOURCE    = 6
NUM_COLS      = 7


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
        return 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        if role == Qt.ItemDataRole.UserRole:
            return self._rows[index.row()]
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        return None


class SongTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.horizontalHeader().hide()
        self.setWordWrap(False)
        self.setMouseTracking(True)

    def set_model(self, model: SongTableModel):
        from gui.song_delegate import SongRowDelegate, ROW_HEIGHT
        self.setModel(model)
        self.setItemDelegate(SongRowDelegate(self))
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT + 6)
        self.horizontalHeader().setStretchLastSection(True)

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

- [ ] **Step 3: Remove tests that no longer apply**

In `tests/test_song_table_model.py`, delete these entire test functions (they test per-column DisplayRole data which no longer exists):

- `test_data_title`
- `test_data_artist`
- `test_data_bpm`
- `test_data_quality`
- `test_data_source`
- `test_data_installed_returns_none_for_display`
- `test_header_data`
- `test_quality_color_complete`
- `test_quality_color_definitive`
- `test_quality_color_official`
- `test_quality_color_other_unchanged`
- `test_background_role_installed_row_is_dark_green`
- `test_background_role_uninstalled_row_is_none`
- `test_background_role_not_set_for_installed_column`

Also remove the import at the bottom of the file:
```python
from gui.song_table import _QUALITY_COLORS
```

Also remove the `COL_TITLE, COL_ARTIST, COL_BPM, COL_QUALITY, COL_SOURCE, COL_INSTALLED` imports from the top of the file since those tests are gone. Keep just `SongTableModel`.

The remaining file should look like this:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtCore import Qt
from gui.song_table import SongTableModel

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
    assert model.columnCount() == 1


def test_display_role_returns_none(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(0, 0)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) is None


def test_user_role_returns_song_dict(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(1, 0)
    song = model.data(idx, Qt.ItemDataRole.UserRole)
    assert song["artist"] == "Nirvana"


def test_get_row(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    assert model.get_row(0)["title"] == "Get Lucky"
    assert model.get_row(1)["artist"] == "Nirvana"


def test_reset_replaces_rows(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    model.reset([SONGS[0]])
    assert model.rowCount() == 1
    assert model.get_row(0)["title"] == "Get Lucky"
```

- [ ] **Step 4: Run model tests**

```
pytest tests/test_song_table_model.py -v
```

Expected: all pass

- [ ] **Step 5: Run full suite**

```
pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add gui/song_table.py tests/test_song_table_model.py
git commit -m "feat: collapse song table to single-column model with SongRowDelegate (Layer 2)"
```

---

### Task 7: FuserLabel widget

**Files:**
- Create: `gui/widgets/__init__.py`
- Create: `gui/widgets/fuser_label.py`

- [ ] **Step 1: Create `gui/widgets/__init__.py`**

Create an empty file at `gui/widgets/__init__.py`.

- [ ] **Step 2: Create `gui/widgets/fuser_label.py`**

```python
from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import (
    QPainter, QLinearGradient, QFont, QColor,
    QPainterPath, QFontMetricsF,
)
from PySide6.QtWidgets import QWidget

from gui.tokens import TOKENS


class FuserLabel(QWidget):
    """FUSER logotype rendered with a multi-stop gradient fill.

    QSS cannot do background-clip:text, so we override paintEvent and fill
    a QPainterPath with a QLinearGradient. The same widget renders any text
    in the FUSER gradient; default is "FUSER".
    """

    def __init__(self, text: str = "FUSER", pt_size: int = 40, parent=None):
        super().__init__(parent)
        self._text = text
        self._pt_size = pt_size
        f = QFont("Sora", pt_size)
        f.setWeight(QFont.Weight.Black)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 104)
        self._font = f
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def setText(self, text: str):
        self._text = text
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        fm = QFontMetricsF(self._font)
        return QSize(int(fm.horizontalAdvance(self._text) + 12),
                     int(fm.height() + 12))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )
        rect = QRectF(self.rect()).adjusted(6, 6, -6, -6)

        # 4-stop gradient: purple → pink → orange → yellow
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.00, QColor(TOKENS["accent_purple"]))
        grad.setColorAt(0.30, QColor(TOKENS["accent_pink"]))
        grad.setColorAt(0.65, QColor(TOKENS["accent_orange"]))
        grad.setColorAt(1.00, QColor(TOKENS["accent_yellow"]))

        path = QPainterPath()
        path.addText(
            rect.left(),
            rect.top() + QFontMetricsF(self._font).ascent(),
            self._font,
            self._text,
        )

        # Soft glow: 8 offset copies in semi-transparent pink before the fill
        glow = QColor(255, 94, 158, 110)
        p.save()
        p.translate(0, 2)
        p.setBrush(glow)
        p.setPen(Qt.PenStyle.NoPen)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (1, 1), (-1, 1), (1, -1)]:
            p.translate(dx, dy)
            p.drawPath(path)
            p.translate(-dx, -dy)
        p.restore()

        # Gradient fill
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)
```

- [ ] **Step 3: Verify FuserLabel can be instantiated**

```bash
python -c "
import sys
from PySide6.QtWidgets import QApplication
import assets_rc
app = QApplication(sys.argv)
from PySide6.QtGui import QFontDatabase, QFont
QFontDatabase.addApplicationFont(':/fonts/Sora-VariableFont_wght.ttf')
app.setFont(QFont('Sora', 10))
from gui.widgets.fuser_label import FuserLabel
lbl = FuserLabel('FUSER', 22)
print('sizeHint:', lbl.sizeHint())
"
```

Expected: prints a QSize with width > 0.

- [ ] **Step 4: Run full suite**

```
pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add gui/widgets/__init__.py gui/widgets/fuser_label.py
git commit -m "feat: add FuserLabel gradient logotype widget (Layer 2)"
```

---

## Layer 3 — Backdrop + polish

### Task 8: StageBackdrop widget

**Files:**
- Create: `gui/widgets/stage_backdrop.py`

- [ ] **Step 1: Create `gui/widgets/stage_backdrop.py`**

```python
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QRadialGradient, QColor
from PySide6.QtWidgets import QWidget


class StageBackdrop(QWidget):
    """Full-window radial gradient backdrop matching the Fuser Battles screen.

    Sits as the lowest child of the central widget. All other widgets are
    transparent, allowing the gradient to show through.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.lower()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QRadialGradient(
            self.width() / 2,
            self.height() * 1.1,
            self.width() * 1.2,
        )
        g.setColorAt(0.00, QColor("#ff5e9e"))
        g.setColorAt(0.22, QColor("#6b2d7a"))
        g.setColorAt(0.50, QColor("#2a0d4a"))
        g.setColorAt(1.00, QColor("#0a0420"))
        p.fillRect(self.rect(), g)
```

- [ ] **Step 2: Verify it imports**

```bash
python -c "from gui.widgets.stage_backdrop import StageBackdrop; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add gui/widgets/stage_backdrop.py
git commit -m "feat: add StageBackdrop radial gradient widget (Layer 3)"
```

---

### Task 9: Wire backdrop and FuserLabel into main window

**Files:**
- Modify: `gui/main_window.py`
- Modify: `tests/test_gui_smoke.py`

- [ ] **Step 1: Write failing smoke tests**

Replace the contents of `tests/test_gui_smoke.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock


def _make_app(qtbot):
    """Boot FuserApp with all external calls mocked out."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (0,)
    with patch("gui.main_window.init_db", return_value=mock_conn), \
         patch("gui.main_window.scan_and_sync"), \
         patch("gui.main_window.get_setting", return_value=None), \
         patch("gui.main_window.get_songs", return_value=[]):
        from gui.main_window import FuserApp
        window = FuserApp()
    qtbot.addWidget(window)
    return window


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


def test_stage_backdrop_is_child_of_central_widget(qtbot):
    from gui.widgets.stage_backdrop import StageBackdrop
    window = _make_app(qtbot)
    children = window.centralWidget().children()
    assert any(isinstance(c, StageBackdrop) for c in children)


def test_fuser_label_in_topbar(qtbot):
    from gui.widgets.fuser_label import FuserLabel
    window = _make_app(qtbot)
    # FuserLabel is inserted into FilterBar's top toolbar layout
    all_widgets = window.findChildren(FuserLabel)
    assert len(all_widgets) >= 1
```

Run to confirm new tests fail:

```
pytest tests/test_gui_smoke.py::test_stage_backdrop_is_child_of_central_widget tests/test_gui_smoke.py::test_fuser_label_in_topbar -v
```

Expected: FAIL on both new tests.

- [ ] **Step 2: Update `gui/main_window.py`**

Add these imports at the top of `gui/main_window.py` (after the existing imports):

```python
from gui.widgets.stage_backdrop import StageBackdrop
from gui.widgets.fuser_label import FuserLabel
```

In `_build_ui`, after `root.setSpacing(0)` and before building `self.filter_bar`, create the backdrop (it will be lowered after siblings exist):

```python
        self._backdrop = StageBackdrop(central)
```

At the very end of `_build_ui` (after `root.addWidget(self.status_bar)`), lower the backdrop below all layout children:

```python
        self._backdrop.lower()
        self._backdrop.resize(central.size())
```

In `_build_ui`, after `root.addWidget(self.filter_bar)`, insert the FuserLabel into the filter bar's top toolbar at position 0:

```python
        self._fuser_lbl = FuserLabel("FUSER", pt_size=22)
        self.filter_bar._top_layout.insertWidget(0, self._fuser_lbl)
```

Add a `resizeEvent` override to `FuserApp` (after `_build_ui`):

```python
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_backdrop"):
            self._backdrop.resize(self.centralWidget().size())
```

- [ ] **Step 3: Run new smoke tests**

```
pytest tests/test_gui_smoke.py -v
```

Expected: all three tests PASS.

- [ ] **Step 4: Run full test suite**

```
pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add gui/main_window.py tests/test_gui_smoke.py
git commit -m "feat: wire StageBackdrop and FuserLabel into main window (Layer 3)"
```

---

## Verification

After all tasks complete, launch the app and confirm:

```
python app.py
```

- [ ] Window background shows the deep purple→pink radial gradient stage backdrop
- [ ] "FUSER" logotype in the topbar renders with the purple→pink→orange→yellow gradient fill and soft pink underglow
- [ ] Song list shows 64px card rows with coloured album-art thumbnails, two text lines (title + artist · source), quality pills, and BPM block
- [ ] Installed songs show a green dot and a green-tinted quality pill
- [ ] Hover over a row lightens it from `surface_4` → `surface_5`
- [ ] Selected row shows `surface_6` background with a pink rim
- [ ] Buttons are pill-shaped (border-radius ≈ 22px)
- [ ] Status bar is a pill floating at the bottom with the dark semi-transparent background
- [ ] `python -c "from PySide6.QtWidgets import QApplication; import assets_rc; from PySide6.QtGui import QFontDatabase, QFont; app = QApplication([]); QFontDatabase.addApplicationFont(':/fonts/Sora-VariableFont_wght.ttf'); app.setFont(QFont('Sora',10)); print(app.font().family())"` prints `Sora`
