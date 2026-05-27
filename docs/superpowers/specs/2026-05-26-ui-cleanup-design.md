# UI Cleanup Design — 2026-05-26

## Overview

Four targeted fixes to the Fuser Custom Song Manager GUI. No new features, no architectural changes.

---

## 1. Layout Scaling (`main_window.py`)

**Problem:** `_build_ui` adds the splitter to the root `QVBoxLayout` with no stretch factor. Qt distributes extra vertical space arbitrarily, inflating the filter bars and starving the song list. Detail panel action buttons are cut off at smaller window heights.

**Fix:** Pass `stretch=1` when adding the splitter:

```python
root.addWidget(splitter, stretch=1)
```

The filter bar and status bar use default `Preferred` size policy so they will occupy only their natural height. All extra vertical space flows to the splitter.

**Files:** `gui/main_window.py` — `_build_ui` method only.

---

## 2. Quality Badge Colours (`song_table.py`)

**Problem:** Current colours (blue/green tones) don't match the user's expected gold/platinum/purple scheme from the original app.

**Fix:** Replace `_QUALITY_COLORS` with the option-C (muted) palette:

| Quality    | Background | Foreground | Description      |
|------------|-----------|-----------|-----------------|
| Complete   | `#2e2000` | `#d4a017` | Ochre / gold     |
| Definitive | `#252530` | `#a0a8b8` | Pewter / silver  |
| Official   | `#1a1535` | `#8b7de8` | Indigo / purple  |
| Other      | `#2a2a2a` | `#888888` | Unchanged        |

**Files:** `gui/song_table.py` — `_QUALITY_COLORS` dict only.

---

## 3. Installed Row Green Background (`song_table.py`)

**Problem:** The model already returns `BackgroundRole` for installed rows, but:
- `InstallDelegate.paint()` ignores it and always fills `#1c1c1c`.
- Default Qt delegate for Title/Artist/BPM/Source columns is overridden by the QSS `alternate-background-color`, so the green never appears.

**Fix — three parts:**

1. Update `BackgroundRole` colour in `SongTableModel.data()` from `#1a2e1a` to `#152215` (the darker green from the chosen palette).

2. Fix `InstallDelegate.paint()` to read `BackgroundRole` instead of hardcoding `#1c1c1c` for unselected rows — same pattern `QualityDelegate` already uses.

3. Add a `_RowBgDelegate(QStyledItemDelegate)` that overrides `initStyleOption` to apply the model's `BackgroundRole` brush before Qt paints the cell. Set it on `COL_TITLE`, `COL_ARTIST`, `COL_BPM`, and `COL_SOURCE` in `SongTableView.set_model()`.

Selection highlight (`#1e3a5f`) takes priority over the green in both custom delegates — no change needed there.

**Files:** `gui/song_table.py` — `SongTableModel.data`, `InstallDelegate.paint`, new `_RowBgDelegate` class, `SongTableView.set_model`.

---

## 4. Window Icon (`assets/` + `main_window.py`)

**Problem:** The old customtkinter app displayed CTk's built-in blue icon. The PySide6 rewrite falls back to the generic Python icon.

**Approach:** Generate a custom `.ico` once using Pillow and commit it to the repo. Pillow is not a runtime dependency.

**Dev script:** `assets/generate_icon.py`
- Draws a dark rounded square (`#1c1c1c`) with a simple music-note glyph (`#2563eb` blue, matching the primary button colour)
- Exports multi-size `.ico`: 16×16, 32×32, 48×48
- Output: `assets/icon.ico`
- Run manually when the icon needs updating: `python assets/generate_icon.py`

**Runtime:** In `FuserApp.__init__`, add after `self.setStyleSheet(APP_STYLE)`:

```python
from PySide6.QtGui import QIcon
self.setWindowIcon(QIcon("assets/icon.ico"))
```

Path is relative to the working directory (project root), which is where `app.py` is launched from.

**Files:** `assets/generate_icon.py` (new), `assets/icon.ico` (generated + committed), `gui/main_window.py` (`__init__` only).

---

## Files Changed Summary

| File | Change |
|------|--------|
| `gui/main_window.py` | Add `stretch=1` to splitter; add `setWindowIcon` call |
| `gui/song_table.py` | Update `_QUALITY_COLORS`; fix `InstallDelegate`; add `_RowBgDelegate`; update `set_model` |
| `assets/generate_icon.py` | New dev script (Pillow) |
| `assets/icon.ico` | Generated icon, committed to repo |

## Out of Scope

- Merging the search and filter rows into one bar
- Configurable row height
- Any changes to the detail panel, batch mode, settings dialog, or data layer
