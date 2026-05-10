# Changelog — Fuser Custom Song Manager

This document tracks notable changes, fixes, and architectural decisions made to the project. Created 2026-05-05.

---

## Fix 1: Downloader — "temp directory already exists" error

**Date:** 2026-05-05
**Files:** `downloader.py`, `tests/test_downloader.py`

### Problem
On Windows, `gdown.download(url, str(work_dir) + "/")` appended a forward slash to a Windows temp path (e.g., `C:\Users\...\tmpXXXXXX/`). The mixed path separator caused `os.path.isdir()` to fail, so gdown tried to create a file at the directory's path, resulting in a "temp directory already exists" error.

### Fix
Let `gdown.download()` determine the output path on its own, then move the returned file into the staging work directory:

```python
output_file = gdown.download(url, quiet=False, fuzzy=True)
if output_file:
    src = Path(output_file)
    shutil.move(str(src), str(work_dir / src.name))
```

### Tests added
- All 13 downloader tests pass (including existing host detection, pair finding, error handling)

---

## Fix 2: Compressed archive extraction (zip/rar/7z)

**Date:** 2026-05-05
**Files:** `downloader.py`, `tests/test_downloader.py`, `requirements.txt`

### Problem
When a Google Drive link returns a compressed folder (zip, rar, 7z, tar.gz, etc.), the downloader extracted no `.pak`/`.sig` files and returned `status: "manual"`, even though the files were inside the archive.

### Solution
Added archive extraction as a fallback in `_gdrive()`:
1. After downloading, check for `.pak`/`.sig` pairs
2. If none found, call `_extract_archives(work_dir)` to find and extract any archives
3. Retry pair discovery after extraction

### Key functions added to `downloader.py`
- **`_extract_archives(work_dir)`** — Scans `work_dir` recursively for archives and extracts them (up to 5 passes for nested archives)
- **`_archive_suffix(path)`** — Detects archive format by extension, handles two-part suffixes like `.tar.gz`
- **`_flatten_into(src, dst)`** — Moves extracted files up one directory level (handles name collisions with `_1`, `_2` suffixes)

### Supported archive formats
| Format | Library | Notes |
|--------|---------|-------|
| `.zip` | `zipfile` (stdlib) | No new dependency |
| `.rar` | `patoolib` | New dependency: `patool==4.0.4` |
| `.7z` | `patoolib` | New dependency |
| `.tar`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.tar.xz` | `patoolib` | New dependency |

### Tests added — 11 new
- `test_archive_suffix_recognises_zip/rar/7z/tar_gz`
- `test_archive_suffix_returns_none_for_plain_file`
- `test_flatten_into_moves_files`, `test_flatten_into_handles_collision`
- `test_extract_archives_zip_with_pak`, `test_extract_archives_zip_no_pak`
- `test_extract_archives_no_archive_is_noop`
- `test_download_gdrive_zip` (end-to-end)

---

## Fix 3: Source retrieval — PACKS tab and NEW SUBMISSIONS

**Date:** 2026-05-05
**Files:** `sources/fucuco.py`, `gui/main_window.py`, `gui/detail_panel.py`, `tests/test_fucuco.py`

### Background
The fucuco Google Sheet has three primary tabs:
1. **FULL DATABASE** — works fine via gviz API (9,464 songs)
2. **VGM** — works fine via gviz API (670 songs)
3. **NEW SUBMISSIONS** — broken via gviz API (returns only 4 rows with `#REF!` errors)
4. **PACKS** — a pack-submission tracker with multi-song content (331 songs)

### Discovery process
The original code referenced three tabs:
```python
TABS = [
    ("FULL DATABASE",   "fucuco_main"),
    ("VGM",             "fucuco_vgm"),
    ("NEW SUBMISSIONS", "fucuco_new"),
]
```

The NEW SUBMISSIONS tab's gviz API returns only 4 rows — the first row is a SEARCH filter control, and subsequent rows contain `#REF!` formula errors. Attempting to adapt the parsing for this format revealed the data was actually coming from a **different tab** via the export API.

### Solution
1. **Removed automated NEW SUBMISSIONS parsing** — the tab is too volatile to parse programmatically. Instead, added a UI link that opens the sheet in the user's browser.
2. **Added PACKS as `fucuco_packs`** — uses the export API (`export?format=csv`) instead of gviz, which returns all 59 rows (52 packs with 331 songs after expansion).
3. **Added `get_sheet_tab_url(source)`** — maps source names to their Google Sheet URLs for the "Browse source sheet" UI feature.
4. **Added `#REF!`/`#N/A` error handling** — Google Sheets formula errors in `normalise_row()` are treated as empty values.

### PACKS tab format
| Column | Content |
|--------|---------|
| Creator | Modder/pack creator name |
| Title | Pack name (stored in `complete_notes`) |
| N° | Number of songs |
| V | Version |
| Download | Host (Google Drive, OneDrive, etc.) |
| Date | Submission date |
| Content | Newline-separated song entries: `Artist - Title` |

### UI changes
**`gui/main_window.py`:**
- Source dropdown updated: `fucuco_new` → `fucuco_packs`

**`gui/detail_panel.py`:**
- Added "Browse source sheet" button — appears for songs without a direct download link (e.g., PACKS songs)
- Added "Browse NEW SUBMISSIONS sheet (latest additions)" link — shown in empty/no-song-selected state
- Download button disabled for linkless songs, directing users to the sheet instead

### Tests added — 12 new (fucuco) + 3 new (sheet URL)
- `test_get_sheet_tab_url_known_source/new_submissions/unknown_source`
- `test_normalise_skips_ref_error_link`, `test_normalise_handles_ref_error_fields`
- `test_is_pack_header_row_positive/negative/partial`
- `test_split_pack_songs_dash/no_dash/empty`
- `test_fetch_pack_tab_success/empty_content_skipped/no_header`
- Updated existing `test_fetch_tab_skips_search_row` for new source parameter

---

## Test suite growth

| Milestone | Tests | Change |
|-----------|-------|--------|
| Original | 44 | — |
| After downloader fix | 44 | +0 (all pass) |
| After archive extraction | 55 | +11 |
| After NEW SUBMISSIONS fix | 67 | +12 |
| After PACKS refactor | 70 | +3 |
| **Final** | **70** | **+26 total** |

---

## Feature: Color-coded quality tiers and Clear Filters button

**Date:** 2026-05-08
**Files:** `gui/song_table.py`, `gui/main_window.py`

### Changes

**`gui/song_table.py`** — Quality column text is now color-coded:
- **Official** → purple (`#bb86fc`)
- **Definitive** → platinum/silver (`#e8e8e8`)
- **Complete** → gold (`#ffd700`)
- **Other** → dim gray (`#888888`)

Colors match the fucuco sheet's convention. Tags are applied as ttk foreground styles and stack with the existing green row background for installed songs.

**`gui/main_window.py`** — New **"Clear Filters"** button at the end of the filter bar resets all filter controls (search, source, quality, status, genre, BPM min/max, sort) back to defaults and triggers a fresh unfiltered query in one click.

---

## Feature: Manual install toggle for manually-downloaded songs

**Date:** 2026-05-08
**Files:** `installer.py`, `gui/detail_panel.py`, `gui/main_window.py`

### Problem
Songs hosted on OneDrive, MediaFire, MEGA, or other non-GDrive hosts return `status: "manual"` from the downloader. The user manually downloads the `.pak`/`.sig` files, but has no way to tell the app "I've finished — mark this as installed". The only workaround was to place files in `custom_songs/<artist>/` and restart the app.

### Solution
Added a **"Mark as Installed (browse .pak…)"** button to the detail panel, positioned between the Download and Uninstall buttons.

**`installer.py`:**
- New function `install_manual_files()` — **copies** (preserves originals) user-selected `.pak`/`.sig` files into `C:\Fuser\Fuser\Content\Paks\custom_songs\<Artist>\` and registers in the DB

**`gui/detail_panel.py`:**
- New `on_manual_install` callback parameter
- "Mark as Installed" button (steel blue, disabled when song is already installed)
- Opens `tkinter.filedialog.askopenfilename()` filtered to `*.pak` files
- Auto-discovers matching `.sig` in the same directory (same stem, `.sig` extension)

**`gui/main_window.py`:**
- `_on_manual_install()` callback wires `install_manual_files`, refreshes table & panel, shows "Installed: {title}" in status bar

### UX flow
1. User clicks Download & Install on a non-GDrive song → sees "Manual download required"
2. User downloads `.pak`/`.sig` manually via the blue link
3. User clicks **Mark as Installed (browse .pak…)** → file dialog opens
4. User selects the `.pak` → app auto-finds `.sig`, copies both to install directory
5. Row turns green with ✓ badge immediately

---

## Fix: Larger table font, row height, and zebra striping for readability

**Date:** 2026-05-08
**Files:** `gui/song_table.py`

### Changes
- Increased table font from 10pt to **11pt** (now uses `TkDefaultFont` as DPI-aware base)
- Row height bumped from 24px to **28px**
- Added **alternating row colors** — even rows use a slightly lighter shade (`#353535`) against the default dark background (`#2b2b2b`), making song lists dramatically easier to scan. The installed-song green tint still overrides the zebra stripe on installed rows.

---

## Feature: Configurable install path via Settings dialog

**Date:** 2026-05-10
**Files:** `db.py`, `installer.py`, `gui/main_window.py`

### Problem
The install directory was hardcoded to `C:\Fuser\Fuser\Content\Paks\custom_songs`. Users with Fuser installed to a different drive or custom path had no way to change it.

### Solution
Added a persistent `settings` table to the SQLite database and a Settings dialog accessible from the top toolbar.

**`db.py`:**
- New `settings` table (key-value pairs)
- `get_setting(conn, key)` and `set_setting(conn, key, value)` functions
- Default install path seeded on first launch

**`installer.py`:**
- Renamed `INSTALL_DIR` → `DEFAULT_INSTALL_DIR` to clarify it's a fallback default
- All functions already accepted `install_root` as a parameter — no signature changes needed

**`gui/main_window.py`:**
- Path loaded from DB into `self._install_dir` at startup
- All install operations use `self._install_dir` instead of the hardcoded constant
- New **"Settings"** button in the top toolbar opens a modal dialog:
  - Shows current path in an editable text field
  - **Browse…** button opens a native directory picker
  - **Save** writes the path to DB, creates it if missing, re-scans for installed files
  - **Cancel** closes without changes

---

## Dependencies added

| Package | Version | Reason |
|---------|---------|--------|
| `patool` | 4.0.4 | RAR/7z/tar archive extraction |
