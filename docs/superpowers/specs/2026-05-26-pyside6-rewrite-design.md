# PySide6 UI Rewrite — Design Spec

**Date:** 2026-05-26
**Scope:** Replace the `gui/` package and `app.py` with a PySide6 implementation. One minimal change to `db.py` is required to support virtual scrolling (see Section 1). All other backend code (`downloader.py`, `installer.py`, `sources/`) is unchanged.

---

## Motivation

The current customtkinter UI has limited styling control — quality badges, install status indicators, and hover states all fight the underlying `ttk.Treeview`. PySide6 (LGPL) provides full QSS styling, proper `QAbstractTableModel`-based virtual scrolling, and clean signal/slot threading. The app will also gain window resizing support and drop pagination in favour of a single scrollable list.

---

## File Structure

Only `gui/` and `app.py` change:

```
gui/
  __init__.py
  main_window.py          # QMainWindow — assembles panels, connects signals
  song_table.py           # SongTableModel + SongTableView + delegates
  detail_panel.py         # QWidget — song info and action buttons
  filter_bar.py           # QWidget — search, dropdowns, BPM, sort, clear
  status_bar.py           # QWidget — progress bar + message label
  settings_dialog.py      # QDialog — install path setting
  batch_results_dialog.py # QDialog — batch download results list
  styles.py               # Single QSS stylesheet string
app.py                    # Entry point — unchanged except PySide6 imports
```

---

## Section 1: Data Model & Virtual Scrolling

`SongTableModel` subclasses `QAbstractTableModel` and holds the filtered result set as a plain Python list. On any filter change, `MainWindow` calls `get_songs()` with no `LIMIT`/`OFFSET` and passes the result to `model.reset(rows)`, which replaces the list and emits `layoutChanged`. `QTableView` handles all scrolling natively — no pagination UI needed.

**Required `db.py` change:** `get_songs()` currently has a hardcoded `LIMIT 100`. It needs an optional `limit` parameter (default `100`, pass `0` for no limit) so the GUI can load all matching rows at once for virtual scrolling. This is a one-line query change with no effect on existing callers.

**Columns:** `[installed, title, artist, bpm, quality, source]`

**Custom delegates:**
- `InstallDelegate` — draws a filled green dot (installed) or hollow grey dot (not installed)
- `QualityDelegate` — draws a colored rounded-rect badge per quality tier (Official, Definitive, Complete, Other)

**Batch mode selection:** `SongTableView.get_selected_songs()` returns all selected rows from the model when in `ExtendedSelection` mode.

Loading the full filtered set into memory at once is sufficient — the song library is a few thousand rows at most.

---

## Section 2: Signals & Threading

Widgets communicate only through signals. No widget holds a direct reference to another.

### Signal flow

| Emitter | Signal | Receiver | Action |
|---|---|---|---|
| `FilterBar` | `filters_changed(dict)` | `MainWindow` | Reload model |
| `SongTableView` | `selectionChanged` | `MainWindow` | Update `DetailPanel` |
| `DetailPanel` | `download_requested(dict)` | `MainWindow` | Start download worker |
| `DetailPanel` | `uninstall_requested(dict)` | `MainWindow` | Run uninstall |
| `DetailPanel` | `manual_install_requested(dict, Path, Path)` | `MainWindow` | Run manual install |
| `MainWindow` | `batch_mode_entered` | panels | Show/hide accordingly |
| `MainWindow` | `batch_mode_exited` | panels | Restore layout |

### Threading

Background work (refresh sources, single download, batch download) runs in `QThread` worker objects. Each worker defines typed signals: `progress(str)`, `finished()`, `error(str)`. Workers emit to the main thread — no `after()` calls or `invokeMethod`. `MainWindow` connects worker signals to status bar and model updates before starting the thread.

This replaces the current `threading.Thread` + `self.after(0, lambda: ...)` pattern.

---

## Section 3: Styling

All visual styling lives in `styles.py` as a single QSS string applied once at startup via `app.setStyleSheet(...)`. No style logic in widget constructors.

**Targets:**

| Element | Notes |
|---|---|
| `QMainWindow`, `QDialog` | Background `#1c1c1c` |
| `QTableView` | Alternating rows, selection `#1e3a5f`, no grid lines, row height 28px |
| `QHeaderView` | Uppercase labels, muted colour, fixed height |
| `QPushButton` | Variants via object name: `#primaryBtn`, `#dangerBtn`, `#mutedBtn` |
| `QComboBox`, `QLineEdit` | Consistent dark input style, border highlight on focus |
| `QScrollBar` | Slim, dark |
| `QStatusBar` | Slightly darker than main background, small font |

The mockup at `.superpowers/brainstorm/*/content/pyqt6-mockup.html` represents the target fidelity.

---

## Section 4: Remaining Components

### Settings dialog
`QDialog` with `QFormLayout`. `QLineEdit` for install path, Browse button via `QFileDialog.getExistingDirectory`, Save/Cancel buttons. If path doesn't exist, shows a `QMessageBox` confirmation before creating it.

### Batch mode
`MainWindow` manages a `_batch_mode` bool. On enter: `DetailPanel` hides, table switches to `ExtendedSelection`, batch toolbar buttons appear. On exit: reverses. Download button label updates live from `selectionChanged`. All batch toolbar buttons live in the filter/pagination area and are shown/hidden as a group.

### Batch results dialog
`QDialog` with a `QScrollArea`. Each result row: icon + title + status message, coloured per status using the same palette as the current app (`#52b788` ok, `#f4a261` manual, `#e76f51` error, `#888888` skipped). Close button exits batch mode.

### Status bar
`QProgressBar` (hidden when idle) beside a `QLabel` for messages. Progress comes from worker `progress(str)` signal. Error messages shown in red via stylesheet property.

---

## Out of Scope

- Backend logic changes beyond the `get_songs()` limit parameter (`downloader.py`, `installer.py`, `sources/`)
- New features beyond what the current app provides
- macOS/Linux packaging (app currently targets Windows)
