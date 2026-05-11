# Cleanup & Batch Download — Design Spec
Date: 2026-05-11

## Overview

Two sequential workstreams:
1. Fix code-review issues identified in three non-Claude commits.
2. Implement batch download with an explicit "Batch Mode" toggle (Option A).

---

## Part 1 — Code Cleanup

Targeted fixes only. No refactoring beyond what is listed.

### 1.1 `StatusBar.set_message(text)`
Add a public `set_message(text: str)` method to `gui/status_bar.py` that sets the label text directly. Update `gui/main_window.py` Settings Save handler to call `self.status_bar.set_message(f"Install path: {new_path}")` instead of `set_idle()` followed by direct `_lbl.configure(...)`.

### 1.2 Settings Save — background thread
Wrap `scan_and_sync()` + `_refresh_table()` in a daemon thread (same pattern as `_start_refresh`). The Save button in the dialog shows "Saving…" and is disabled while the thread runs. The dialog remains open until the thread completes, then closes automatically on the main thread via `self.after(0, dialog.destroy)`.

### 1.3 Settings Save — mkdir confirmation
When the typed path does not exist, show a confirmation `CTkToplevel` before creating it: "Directory does not exist — create it?" with Yes / No buttons. If the user chooses No, the Settings dialog stays open. If Yes, proceed with `mkdir(parents=True, exist_ok=True)` then save.

### 1.4 Rename `"evenrow"` tag to `"altrow"`
In `gui/song_table.py`, rename every occurrence of the `"evenrow"` tag string (`tag_configure`, `tags.append`, and the stack comment) to `"altrow"`. The tag is applied to odd-indexed rows (`i % 2 == 1`); the old name was semantically backwards.

### 1.5 Remove unused `entry` variable
In `gui/main_window.py` `_open_settings`, the `CTkEntry` is assigned to `entry` but never read again. Remove the variable assignment; the widget is already packed/gridded by the call itself.

### 1.6 Remove redundant `conn.commit()` in `db.py`
`set_setting()` already calls `conn.commit()` internally. Remove the redundant `conn.commit()` that follows the `set_setting()` call in `init_db()` (around line 158).

### 1.7 New tests in `test_db.py`
Add four tests:
- `test_settings_table_created` — after `init_db()`, the `settings` table exists.
- `test_get_set_setting` — `set_setting` persists a value; `get_setting` retrieves it; `get_setting` returns `None` for unknown keys.
- `test_init_db_seeds_default_install_path` — `init_db()` on a fresh DB writes a default `install_path` value to the settings table (confirmed: `db.py:156-157` does this).
- `test_init_db_does_not_overwrite_existing_setting` — calling `init_db()` a second time on the same DB does not overwrite a user-saved `install_path`.

---

## Part 2 — Batch Download (Option A)

### 2.1 UX Behavior

**Normal mode (default):**
- Table: `selectmode="browse"` (single-select)
- Detail panel: visible (right column, weight=3)
- Pagination bar: shows "← Prev", page label, "Next →", and a new "Batch" button on the right

**Batch mode (active):**
- Table: `selectmode="extended"` (multi-select, Shift-click + Ctrl-click)
- Detail panel: hidden (column weight set to 0, widget unpacked/hidden)
- Table column expands to fill freed space (column 0 weight increases)
- Pagination bar: "Batch" button replaced by "Select All" | "Deselect All" | "✕ Exit Batch" | "Download (0)" (green, disabled until selection ≥ 1)
- "Download (N)" label updates as selection changes

**Exiting batch mode:**
Triggered by: clicking "✕ Exit Batch", or when a batch download completes. Resets: clears selection, restores `"browse"` selectmode, restores detail panel column weight, swaps pagination buttons back.

### 2.2 Download Flow

- Filters selected songs to uninstalled only (songs without `pak_path`)
- If all selected songs are already installed, shows results dialog immediately with "Already installed" status for each
- Downloads run sequentially in a daemon thread (no parallelism)
- Status bar shows `[1/3] Downloading: Song Title` during the run
- "Download (N)" button goes disabled and shows "Downloading…" during run
- On completion: calls `_refresh_table()`, shows results dialog (existing `_show_batch_results` pattern), then auto-exits batch mode

### 2.3 `SongTable` Interface Changes

New constructor parameter: `on_selection_change: Callable | None = None`

New public methods:
- `select_all()` — selects all rows on the current page
- `deselect_all()` — clears all selections
- `get_selected_songs() -> list[dict]` — returns song dicts for all selected rows
- `set_selectmode(mode: str)` — switches between `"browse"` and `"extended"` on the underlying Treeview

`on_selection_change` is called from `_on_tree_select` and from `select_all` / `deselect_all`.

### 2.4 `MainWindow` Changes

New state: `self._batch_mode: bool = False`

New methods:
- `_enter_batch_mode()` — sets `_batch_mode=True`, hides detail panel, swaps buttons, changes table selectmode
- `_exit_batch_mode()` — resets all of the above
- `_on_selection_change()` — updates "Download (N)" button count and enabled state
- `_on_batch_download()` — validates selection, disables button, starts background thread
- `_do_batch_download(songs)` — sequential download loop with status bar updates
- `_show_batch_results(results)` — modal dialog (re-implement from the previously reverted commit)

### 2.5 Out of Scope

- Parallel / concurrent batch downloads
- Progress bar per individual song during batch
- Persisting batch selection across page changes
- Batch uninstall

---

## Test Plan

- `test_db.py`: four new settings tests (see 1.7)
- `test_gui_smoke.py`: smoke-import still passes after all changes
- Manual verification: enter/exit batch mode, select all/deselect all, download 2–3 songs, verify results dialog, verify detail panel restores
