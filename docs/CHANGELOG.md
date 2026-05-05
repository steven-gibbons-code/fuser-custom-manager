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

## Dependencies added

| Package | Version | Reason |
|---------|---------|--------|
| `patool` | 4.0.4 | RAR/7z/tar archive extraction |