# Fuser Custom Manager — Full Visual Redesign

**Date:** 2026-05-26  
**Source:** Design system handoff at `https://api.anthropic.com/v1/design/h/UfTE5MR7Dl0aZuNAd_3-bw`  
**Supersedes:** `2026-05-26-ui-cleanup-design.md` (cleanup plan abandoned in favour of this full redesign)

---

## Overview

Replace the current muted "code-editor dark" aesthetic with Fuser the game's visual language: deep navy-to-purple stage backdrop, the pink→orange FUSER gradient, Sora typeface, 64px card rows with album-art thumbnails, pill controls, and glow accents.

Implementation is split into three shippable layers. Each layer builds on the previous and can be committed independently.

---

## Layer 1 — Foundation (tokens, QSS, font, resources)

### `gui/tokens.py` (new)

Design tokens as a Python dict — the single source of truth for every colour and gradient. No existing file references it yet; all other layers import from it.

**Contents:**
- `TOKENS` dict: surfaces (6 steps, `#0a0420` → `#4a2a6f`), accent colours (pink `#ff5e9e`, orange `#ff8a5b`, purple `#c14fff`, yellow `#ffd166`), solid accents (selection purple, success green, warning amber, danger red), stem colours (DJ blue, Bass green, Synth yellow, Vocals red), text ramp (white → soft lavender → muted violet → disabled), tier pill pairs (bg as `rgba(…)` string, fg as hex).
- `GRADIENTS` dict: `fuser` (horizontal pink→orange), `fuser_logo` (diagonal 4-stop), `stage` (radial bottom-center pink→purple→near-black).
- `C(name, alpha=None) → QColor` helper for use in paint code.

### `gui/styles.py` (full replacement)

Delete existing contents. New file is a `.format(**TOKENS, **GRADIENTS)` template. Token references use `{key}` syntax; literal braces in QSS are escaped as `{{` / `}}`.

**Key visual changes from old QSS:**
- Background: `#1a0b32` (surface_2) replaces `#1c1c1c`
- Font: `"Sora"` replaces `"Segoe UI"` throughout
- Buttons: `border-radius: 22px` (pill) replaces `4px`
- Table: `background: transparent`, no gridlines, no alternating row colour
- Status bar: `border-radius: 22px` (pill), `background: rgba(10,4,32,0.6)`
- Detail panel: `border-radius: 20px`, `border: 1px solid rgba(255,255,255,0.05)`
- Scrollbar handles: `rgba(255,255,255,0.1)` replaces solid grey
- QSS gotchas observed: `border-radius: 999px` clips badly in Qt — always use pixel half-height values; `padding` on `QLineEdit` must be paired with `min-height` on Windows.

### Sora font

Download `Sora-VariableFont_wght.ttf` from Google Fonts (Apache 2.0) into `assets/fonts/`. Commit the file. Do not add Pillow or any other new runtime dependency.

### `assets.qrc`

Qt resource file at project root referencing:
- `fonts/Sora-VariableFont_wght.ttf`
- All 16 icon PNGs already at `assets/icons/instruments/` and `assets/icons/utility/`

Build command (run once, commit output): `pyside6-rcc assets.qrc -o assets_rc.py`

### `app.py` (updated boot sequence)

Replace current minimal boot with:
1. `import assets_rc` (registers Qt resources before any widget is created)
2. `QFontDatabase.addApplicationFont(":/fonts/Sora-VariableFont_wght.ttf")`
3. `app.setFont(QFont("Sora", 10))`
4. `QPixmapCache.setCacheLimit(20_000)` (KB, for album-art gradient cache)
5. `app.setStyleSheet(APP_STYLE)` — moves here from `main_window.py`

Remove `self.setStyleSheet(APP_STYLE)` from `FuserApp.__init__`.

### Layer 1 test changes

No model or delegate changes. Existing tests should pass unchanged. Smoke test (`test_gui_smoke.py`) confirms the app launches without error under the new boot sequence.

---

## Layer 2 — Card rows (SongRowDelegate + single-column model + FuserLabel)

### `gui/song_delegate.py` (new)

`SongRowDelegate(QStyledItemDelegate)` paints the entire row in one `paint()` call. The existing per-column delegates (`InstallDelegate`, `QualityDelegate`, `_RowBgDelegate`) are replaced entirely.

**Row anatomy (left → right, 64px tall):**
- Install dot: 5px radius circle, `success` green if installed, dim white-alpha if not. At x=19 from card left.
- Album art: 48×48 rounded (10px radius) gradient square from `_art_pixmap(song["id"])`. At x=36 from card left.
- Text block: title (Sora 11 DemiBold, `fg_white`, elided) on line 1; subline (artist · source · key, Sora 9 Medium, `fg_muted`, elided) on line 2. Right edge stops short of pill + BPM area.
- Quality pill: 100×22px, rounded (half-height radius), per-tier rgba fill + foreground from tokens. If installed, fill switches to `success` alpha tint and label prepends "✓ ".
- BPM block: large number (Sora 13 DemiBold, `fg_white`) + "BPM" caption (Sora 8 Medium, `fg_tertiary`).

**Card background states:**
- Rest: `surface_4` (`#2a1845`)
- Hover: `surface_5` (`#3a205a`)
- Selected: `surface_6` (`#4a2a6f`) + 1px `accent_pink` (alpha 0.5) rim drawn around the rounded-rect path

**Card geometry:** inset 3px top/bottom from `opt.rect` to create a 6px visual gap between cards. Corner radius 14px.

**Inner top-edge highlight:** 1px line at `card.top() + 0.5`, `rgba(255,255,255,12)`, between the rounded corners — mimics the game's glassy inner-stroke.

**`_art_pixmap(song_id, size=48) → QPixmap`:** Cached in `QPixmapCache` by key `"art_{id}_{size}"`. Draws a `QLinearGradient` fill through a rounded-rect `QPainterPath` using one of 8 stable palettes (index = `abs(id) % 8`). Adds a 1px white-alpha inner stroke.

**`_draw_pill(p, x, y, w, h, quality, installed)`:** private method on the delegate; handles the `rgba(…)` token string parsing via regex.

### `gui/song_table.py` (model collapse to single column)

`SongTableModel`:
- `columnCount` returns `1`
- `data(index, role)`: `DisplayRole` returns `None` (delegate paints everything); `UserRole` still returns the full song dict; `BackgroundRole` removed (delegate handles background directly); `CheckStateRole` preserved for batch mode on column 0.
- All `COL_*` constants kept for internal use in `data()` logic but the view no longer maps columns to them.

`SongTableView.set_model`:
- Replace all `setItemDelegateForColumn` calls with `self.setItemDelegate(SongRowDelegate(self))`
- `self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT + 6)` (70px total slot)
- `self.horizontalHeader().hide()`
- `self.setShowGrid(False)`
- `self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)`
- Remove all `setColumnWidth` and `setSectionResizeMode` calls

### `gui/widgets/fuser_label.py` (new)

`FuserLabel(QWidget)` — gradient FUSER logotype:
- Font: Sora 800 (Black weight), default `pt_size=40`, letter spacing 104%
- `paintEvent`: builds `QPainterPath` via `path.addText(...)`, fills with 4-stop `QLinearGradient` (purple→pink→orange→yellow matching `fuser_logo` gradient stops), then draws 8 offset copies in `rgba(255,94,158,110)` as a blur-substitute glow before the main fill
- `sizeHint`: derived from `QFontMetricsF`
- `WA_TranslucentBackground` set so the stage gradient shows through

### Layer 2 test changes

- `test_song_table_model.py`: update `columnCount` assertion to `== 1`; remove `BackgroundRole` tests (model no longer returns it); remove `_QUALITY_COLORS` import tests (dict still exists in delegate, not model)
- `test_song_table_model.py`: add `sizeHint` smoke — `SongRowDelegate().sizeHint(opt, idx).height() == 64`
- All other existing tests should pass; per-column delegate tests that referenced `InstallDelegate` / `QualityDelegate` are deleted

---

## Layer 3 — Backdrop + polish

### `gui/widgets/stage_backdrop.py` (new)

`StageBackdrop(QWidget)`:
- `WA_StyledBackground = False` so QSS doesn't paint over it
- `paintEvent`: `QRadialGradient` centred at `(width/2, height*1.1)`, radius `width*1.2`. Stops: `#ff5e9e` at 0.0, `#6b2d7a` at 0.22, `#2a0d4a` at 0.50, `#0a0420` at 1.0. `fillRect` with the gradient.
- No children; sits below all other widgets via `lower()`

### `gui/main_window.py` (three additions)

1. **StageBackdrop**: instantiate as first child of `centralWidget()`, call `.lower()` after all other children are added.
2. **resizeEvent**: override to resize backdrop to `self.centralWidget().size()` on every resize event (call `super().resizeEvent(event)` first).
3. **FuserLabel**: replace the plain `QLabel` app-title widget in the topbar with `FuserLabel("FUSER", pt_size=22)`. Import from `gui.widgets.fuser_label`.

Remove `self.setStyleSheet(APP_STYLE)` if still present (moved to `app.py` in Layer 1).

### Layer 3 test changes

`test_gui_smoke.py` extended:
- Assert `FuserLabel` instance exists somewhere in the topbar widget tree
- Assert `StageBackdrop` is a direct child of `centralWidget()`

---

## Files Changed Summary

| File | Layer | Change |
|---|---|---|
| `gui/tokens.py` | 1 | New — design tokens |
| `gui/styles.py` | 1 | Full replacement — new QSS template |
| `assets/fonts/Sora-VariableFont_wght.ttf` | 1 | New — downloaded from Google Fonts |
| `assets.qrc` | 1 | New — Qt resource file |
| `assets_rc.py` | 1 | Generated + committed (output of pyside6-rcc on assets.qrc) |
| `app.py` | 1 | Updated boot sequence |
| `gui/song_delegate.py` | 2 | New — SongRowDelegate + _art_pixmap |
| `gui/song_table.py` | 2 | Model collapses to 1 column; delegate wiring replaced |
| `gui/widgets/__init__.py` | 2 | New (empty package) |
| `gui/widgets/fuser_label.py` | 2 | New — FuserLabel gradient widget |
| `gui/widgets/stage_backdrop.py` | 3 | New — StageBackdrop radial gradient |
| `gui/main_window.py` | 3 | StageBackdrop + resizeEvent + FuserLabel in topbar |
| `tests/test_song_table_model.py` | 2 | Update column-count assertion; remove obsolete tests |
| `tests/test_gui_smoke.py` | 3 | Add FuserLabel + StageBackdrop presence assertions |

---

## Out of Scope

- Detail panel conversion (future: convert `detail_panel.py` label styling to use token colours)
- Filter chip strip (future: replace QComboBox row with pill-button scroll area)
- Primary CTA glow (`QGraphicsDropShadowEffect` on Refresh/Download buttons)
- FUSER logo pulse animation (`QPropertyAnimation` on glow strength, 6s loop)
- Progress bar shimmer (gradient pan animation on `QProgressBar::chunk`)
- Star particle backdrop decoration
- Real album-art fetching (Spotify / iTunes Search API)
- `prefers-reduced-motion` / "Reduce motion" settings toggle

---

## Design Token Source of Truth

If any value in this document disagrees with the extracted `colors_and_type.css` from the design package, **`colors_and_type.css` wins**.
