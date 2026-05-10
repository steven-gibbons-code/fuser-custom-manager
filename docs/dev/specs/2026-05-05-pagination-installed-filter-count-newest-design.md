# Pagination, Installed Filter, Result Count, Newest Additions — Design Spec

**Date:** 2026-05-05

## Goal

Four UI/data improvements: browsable pagination beyond 100 rows, an installed/not-installed filter, a visible result count, and a "Newest First" sort using the fucuco Submit Date field.

---

## 1. Pagination (prev/next)

### DB layer

New function in `db.py`:

```python
def count_songs(conn: sqlite3.Connection, filters: dict) -> int:
```

Same WHERE clause construction as `get_songs` (search, source, genre, quality, installed, bpm_min/max) but executes `SELECT COUNT(*) FROM songs s LEFT JOIN installed i ON i.song_id = s.id WHERE ...` and returns a single integer.

`get_songs` already accepts `offset` in filters and applies `LIMIT 100 OFFSET ?`. No changes needed there.

### UI layer (`gui/main_window.py`)

- `_page: int = 0` instance variable, reset to 0 on any filter change
- New **pagination bar** (Row 2, between filter bar and table — table moves to Row 3, status bar to Row 4):
  ```
  [← Prev]   Page 1 of 104   (10,375 songs)   [Next →]
  ```
- `_refresh_table()` injects `offset = self._page * 100` into the filters dict, calls `count_songs` to update the label
- Prev button disabled when `_page == 0`; Next button disabled when `(_page + 1) * 100 >= total`

---

## 2. Installed Filter

### DB layer

`get_songs` gains an `installed` filter key:
- `"installed"` → appends `i.pak_path IS NOT NULL`
- `"not_installed"` → appends `i.pak_path IS NULL`

`count_songs` applies the same `installed` filter.

### UI layer

Dropdown in filter bar after Quality: `All | Installed | Not installed`  
Stored in `self._installed` StringVar, default `"All"`.

---

## 3. Result Count

Shown inline in the pagination bar label: `Page X of Y  (Z songs)`.  
No separate widget — reuses the pagination label. `count_songs` is always called in `_refresh_table`.

---

## 4. Newest Additions (submit_date)

### DB layer

New column `submit_date TEXT` on the `songs` table. Added via non-destructive `_migrate_add_columns` (already handles arbitrary new columns). `s.submit_date` added to `_ALLOWED_ORDER` in `get_songs`.

### Source layer (`sources/fucuco.py`)

`normalise_row` adds `submit_date` key: value from the `"Submit Date"` column, stored as-is (sheet format is `YYYY/MM/DD` which sorts correctly as a string). Blank → `None`.

### UI layer

**Sort** dropdown added to filter bar (rightmost):  
`Artist A–Z` | `Newest First` | `BPM ↑` | `BPM ↓`

Mappings:
- `Artist A–Z` → `order_by="s.artist"`, `descending=False` (default)
- `Newest First` → `order_by="s.submit_date"`, `descending=True`
- `BPM ↑` → `order_by="s.bpm"`, `descending=False`
- `BPM ↓` → `order_by="s.bpm"`, `descending=True`

Changing sort resets page to 0.

---

## Files Changed

| File | Changes |
|------|---------|
| `db.py` | `count_songs`, `submit_date` in schema + migration, `installed` filter in `get_songs` + `count_songs`, `s.submit_date` in allowed order |
| `sources/fucuco.py` | `submit_date` added to `normalise_row` |
| `gui/main_window.py` | Pagination bar (new row), installed dropdown, sort dropdown, `_page` counter, `_refresh_table` updated |
| `tests/test_db.py` | Tests for `count_songs`, installed filter, `submit_date` in upsert/query |
| `tests/test_fucuco.py` | Test for `submit_date` in `normalise_row` |
