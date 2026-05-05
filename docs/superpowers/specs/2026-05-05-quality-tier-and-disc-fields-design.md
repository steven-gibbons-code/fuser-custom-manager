# Quality Tier and Disc Fields — Design Spec

**Date:** 2026-05-05

## Goal

Surface a four-tier quality classification (Official / Definitive / Complete / Other) as a visible column in the song table, and expose the Disc 1–4 instrument fields in the song detail panel.

---

## Quality Tiers

| Tier | Definition |
|------|-----------|
| **Official** | `download_type` is non-empty AND is not a URL (`"://"` not in value) — e.g. "DLC", "Base Game", "Diamond Shop" |
| **Definitive** | `complete == 'D'` OR (`de_status == 'Eligible'` AND `complete == 'C'`) OR (`de_status` blank AND `complete == 'C'` AND `complete_notes` blank) |
| **Complete** | `complete == 'C'` and not Definitive and not Official |
| **Other** | Everything else |

Official takes precedence over Definitive if both conditions are met (i.e. a base-game track is Official regardless of its complete value).

---

## Schema Changes (`db.py`)

Five new columns on the `songs` table:

```sql
disc1         TEXT,   -- instrument on disc 1, e.g. "Drums"
disc2         TEXT,   -- instrument on disc 2, e.g. "Vocals"
disc3         TEXT,   -- instrument on disc 3, e.g. "Sampler"
disc4         TEXT,   -- instrument on disc 4, e.g. "Chords"
download_type TEXT,   -- raw Download column value: "DLC", "Base Game", "Diamond Shop", or a URL/blank
quality       TEXT    -- computed tier: "Official" | "Definitive" | "Complete" | "Other"
```

**Migration:** `init_db` detects missing columns via `PRAGMA table_info(songs)` and issues `ALTER TABLE songs ADD COLUMN` for each missing one. No table drop — existing `installed` records are preserved.

---

## Quality Derivation

`quality` is computed in `upsert_songs` before INSERT/UPDATE, not stored by the source fetcher. A helper function `derive_quality(song: dict) -> str` encapsulates the logic:

```python
def derive_quality(song: dict) -> str:
    dt = (song.get("download_type") or "").strip()
    is_official = bool(dt) and "://" not in dt and not dt.lower().startswith("http")
    if is_official:
        return "Official"
    c = (song.get("complete") or "").strip()
    de = (song.get("de_status") or "").strip()
    notes = (song.get("complete_notes") or "").strip()
    is_definitive = (
        c == "D"
        or (de == "Eligible" and c == "C")
        or (not de and c == "C" and not notes)
    )
    if is_definitive:
        return "Definitive"
    if c == "C":
        return "Complete"
    return "Other"
```

Each song dict passed to `upsert_songs` gets `song["quality"] = derive_quality(song)` prepended.

---

## Source Changes (`sources/fucuco.py`)

`normalise_row` adds five new keys to its return dict:

| Key | Sheet column | Notes |
|-----|-------------|-------|
| `disc1` | `Disc 1 ` | Trailing-space handled by `_find` |
| `disc2` | `Disc 2 ` | |
| `disc3` | `Disc 3 ` | |
| `disc4` | `Disc 4 ` | |
| `download_type` | `Download` | May be "DLC", "Base Game", "Google Drive", or blank |

`quality` is NOT set in `normalise_row` — it is computed in `upsert_songs`.

---

## Table Changes (`gui/song_table.py`)

Replace the `definitive` column with `quality`, placed second (after `status`):

```
status | quality | artist | title | creator | BPM | key | genre | year | source
```

Display values in the quality cell:
- `"Official"` → `"Off"`
- `"Definitive"` → `"Def"`
- `"Complete"` → `"Cmp"`
- `"Other"` → `""` (blank — reduces visual noise for the majority of rows)

Column width: 45px.

---

## Detail Panel Changes (`gui/detail_panel.py`)

Add four fields to `_FIELDS` after `origin`:

```python
("disc1", "Disc 1"),
("disc2", "Disc 2"),
("disc3", "Disc 3"),
("disc4", "Disc 4"),
```

Blank disc values display as `"—"` (existing behaviour for empty fields).

---

## Files Changed

| File | Change |
|------|--------|
| `db.py` | Add 6 columns, `ALTER TABLE` migration, `derive_quality` helper, update `upsert_songs` |
| `sources/fucuco.py` | Add `disc1–4`, `download_type` to `normalise_row` return dict |
| `gui/song_table.py` | Replace `definitive` column with `quality` |
| `gui/detail_panel.py` | Add `disc1–4` to `_FIELDS` |
| `tests/test_db.py` | Tests for `derive_quality` and schema migration |
| `tests/test_fucuco.py` | Tests for new normalise_row keys |
