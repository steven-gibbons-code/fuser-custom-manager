import sqlite3
from datetime import datetime
from pathlib import Path

DB_DIR = Path.home() / ".fuser_manager"
DB_PATH = DB_DIR / "catalog.db"
ART_DIR = DB_DIR / "art"

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id             INTEGER PRIMARY KEY,
    source         TEXT NOT NULL,
    artist         TEXT,
    title          TEXT,
    creator        TEXT,
    genre          TEXT,
    year           INTEGER,
    bpm            INTEGER,
    key            TEXT,
    de_status      TEXT,
    complete       TEXT,
    complete_notes TEXT,
    stream_opt     INTEGER DEFAULT 0,
    origin         TEXT,
    link           TEXT,
    link_host      TEXT,
    last_seen      TEXT,
    disc1          TEXT,
    disc2          TEXT,
    disc3          TEXT,
    disc4          TEXT,
    download_type  TEXT,
    quality        TEXT,
    submit_date    TEXT,
    UNIQUE(source, link)
);

CREATE TABLE IF NOT EXISTS album_art (
    id      INTEGER PRIMARY KEY,
    artist  TEXT NOT NULL,
    album   TEXT NOT NULL,
    art_url TEXT,
    UNIQUE(artist, album)
);

CREATE TABLE IF NOT EXISTS installed (
    id           INTEGER PRIMARY KEY,
    song_id      INTEGER UNIQUE REFERENCES songs(id) ON DELETE CASCADE,
    pak_path     TEXT NOT NULL,
    sig_path     TEXT,
    installed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_IS_DEFINITIVE = """
CASE
    WHEN s.complete = 'D' THEN 1
    WHEN s.de_status = 'Eligible' AND s.complete = 'C' THEN 1
    WHEN (s.de_status IS NULL OR s.de_status = '')
         AND s.complete = 'C'
         AND (s.complete_notes IS NULL OR s.complete_notes = '') THEN 1
    ELSE 0
END
"""


_OFFICIAL_LABELS = {"dlc", "base game", "diamond shop"}

def derive_quality(song: dict) -> str:
    dt = (song.get("download_type") or "").strip().lower()
    if dt in _OFFICIAL_LABELS:
        return "Official"
    c     = (song.get("complete")       or "").strip()
    de    = (song.get("de_status")      or "").strip()
    notes = (song.get("complete_notes") or "").strip()
    is_def = (
        c == "D"
        or (de == "Eligible" and c == "C")
        or (not de and c == "C" and not notes)
    )
    if is_def:
        return "Definitive"
    if c == "C":
        return "Complete"
    return "Other"


def _build_where_params(filters: dict) -> tuple[list[str], list]:
    where, params = ["1=1"], []
    if filters.get("search"):
        where.append("(s.artist LIKE ? OR s.title LIKE ? OR s.creator LIKE ?)")
        t = f"%{filters['search']}%"
        params += [t, t, t]
    if filters.get("source"):
        where.append("s.source = ?")
        params.append(filters["source"])
    if filters.get("genre"):
        where.append("s.genre LIKE ?")
        params.append(f"%{filters['genre']}%")
    if filters.get("key"):
        where.append("s.key = ?")
        params.append(filters["key"])
    if filters.get("de_status"):
        where.append("s.de_status = ?")
        params.append(filters["de_status"])
    if filters.get("quality"):
        where.append("s.quality = ?")
        params.append(filters["quality"])
    if filters.get("definitive_only"):
        where.append("s.quality IN ('Definitive', 'Official')")
    if filters.get("bpm_min") is not None:
        where.append("s.bpm >= ?")
        params.append(filters["bpm_min"])
    if filters.get("bpm_max") is not None:
        where.append("s.bpm <= ?")
        params.append(filters["bpm_max"])
    if filters.get("installed") == "installed":
        where.append("i.pak_path IS NOT NULL")
    elif filters.get("installed") == "not_installed":
        where.append("i.pak_path IS NULL")
    return where, params


def _migrate_add_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(songs)").fetchall()}
    new_cols = [
        ("disc1",         "TEXT"),
        ("disc2",         "TEXT"),
        ("disc3",         "TEXT"),
        ("disc4",         "TEXT"),
        ("download_type", "TEXT"),
        ("quality",       "TEXT"),
        ("submit_date",   "TEXT"),
        ("art_url",       "TEXT"),
        ("album_art_id",  "INTEGER REFERENCES album_art(id)"),
    ]
    first_album_art_migration = "album_art_id" not in existing
    for col_name, col_type in new_cols:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE songs ADD COLUMN {col_name} {col_type}")
    conn.commit()

    if first_album_art_migration and ART_DIR.exists():
        for f in ART_DIR.glob("*.jpg"):
            try:
                f.unlink()
            except Exception:
                pass


def _needs_migration(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='songs'"
    ).fetchone()
    if not row:
        return False
    # Old schema used UNIQUE(source, artist, title); new uses UNIQUE(source, link)
    return "artist, title" in row[0].lower()


def _dedup_album_art_by_url(conn: sqlite3.Connection) -> None:
    """Merge album_art records that share the same art_url into a single canonical record.

    Fixes duplicates created when song titles were mistakenly used as album keys.
    Idempotent — groups with COUNT > 1 will be empty after the first run.
    """
    dup_urls = conn.execute(
        "SELECT art_url FROM album_art WHERE art_url IS NOT NULL "
        "GROUP BY art_url HAVING COUNT(*) > 1"
    ).fetchall()

    if not dup_urls:
        return

    for row in dup_urls:
        art_url = row["art_url"]
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM album_art WHERE art_url = ? ORDER BY id", (art_url,)
        ).fetchall()]

        # Prefer the record whose file already exists; fall back to lowest id.
        canonical_id = ids[0]
        for aid in ids:
            if (ART_DIR / f"{aid}.jpg").exists():
                canonical_id = aid
                break

        non_canonical = [i for i in ids if i != canonical_id]
        if not non_canonical:
            continue

        # If canonical has no file but a non-canonical does, adopt that file.
        canonical_file = ART_DIR / f"{canonical_id}.jpg"
        if not canonical_file.exists():
            for nc_id in non_canonical:
                nc_file = ART_DIR / f"{nc_id}.jpg"
                if nc_file.exists():
                    try:
                        nc_file.rename(canonical_file)
                    except Exception:
                        pass
                    break

        placeholders = ",".join("?" * len(non_canonical))
        conn.execute(
            f"UPDATE songs SET album_art_id = ? WHERE album_art_id IN ({placeholders})",
            [canonical_id, *non_canonical],
        )
        conn.execute(
            f"DELETE FROM album_art WHERE id IN ({placeholders})",
            non_canonical,
        )

        # Remove any remaining non-canonical files.
        for nc_id in non_canonical:
            nc_file = ART_DIR / f"{nc_id}.jpg"
            try:
                nc_file.unlink(missing_ok=True)
            except Exception:
                pass

    conn.commit()


def init_db(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if _needs_migration(conn):
        conn.executescript("DROP TABLE IF EXISTS installed; DROP TABLE IF EXISTS songs;")
    conn.executescript(SCHEMA)
    _migrate_add_columns(conn)
    _dedup_album_art_by_url(conn)
    # Ensure default install path setting exists
    if get_setting(conn, "install_path") is None:
        set_setting(conn, "install_path", str(Path(r"C:\Fuser\Fuser\Content\Paks\custom_songs")))
    return conn


def upsert_songs(conn: sqlite3.Connection, songs: list[dict]) -> None:
    enriched = []
    for s in songs:
        s = dict(s)
        s.setdefault("disc1", None)
        s.setdefault("disc2", None)
        s.setdefault("disc3", None)
        s.setdefault("disc4", None)
        s.setdefault("download_type", None)
        s.setdefault("submit_date", None)
        s.setdefault("art_url", None)
        s["quality"] = derive_quality(s)
        enriched.append(s)
    conn.executemany("""
        INSERT INTO songs (source, artist, title, creator, genre, year, bpm, key,
                           de_status, complete, complete_notes, stream_opt, origin,
                           link, link_host, last_seen,
                           disc1, disc2, disc3, disc4, download_type, quality, submit_date,
                           art_url)
        VALUES (:source, :artist, :title, :creator, :genre, :year, :bpm, :key,
                :de_status, :complete, :complete_notes, :stream_opt, :origin,
                :link, :link_host, :last_seen,
                :disc1, :disc2, :disc3, :disc4, :download_type, :quality, :submit_date,
                :art_url)
        ON CONFLICT(source, link) DO UPDATE SET
            artist=excluded.artist, title=excluded.title,
            creator=excluded.creator, genre=excluded.genre, year=excluded.year,
            bpm=excluded.bpm, key=excluded.key, de_status=excluded.de_status,
            complete=excluded.complete, complete_notes=excluded.complete_notes,
            stream_opt=excluded.stream_opt, origin=excluded.origin,
            link_host=excluded.link_host, last_seen=excluded.last_seen,
            disc1=excluded.disc1, disc2=excluded.disc2,
            disc3=excluded.disc3, disc4=excluded.disc4,
            download_type=excluded.download_type, quality=excluded.quality,
            submit_date=COALESCE(excluded.submit_date, submit_date),
            art_url=COALESCE(excluded.art_url, art_url)
    """, enriched)
    conn.commit()


def get_songs(conn: sqlite3.Connection, filters: dict, limit: int = 100) -> list[dict]:
    where, params = _build_where_params(filters)

    _ALLOWED_ORDER = {
        "s.artist", "s.title", "s.creator", "s.bpm", "s.year",
        "s.genre", "s.key", "s.source", "s.de_status", "s.quality",
        "s.submit_date",
    }
    order = filters.get("order_by", "s.artist")
    if order not in _ALLOWED_ORDER:
        order = "s.artist"
    direction = "DESC" if filters.get("descending") else "ASC"

    sql = f"""
        SELECT s.*, {_IS_DEFINITIVE} AS is_definitive,
               i.pak_path, i.sig_path, i.installed_at
        FROM songs s
        LEFT JOIN installed i ON i.song_id = s.id
        WHERE {' AND '.join(where)}
        ORDER BY {order} {direction}, s.id DESC
    """
    if limit > 0:
        offset = filters.get("offset", 0)
        sql += "\n        LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def count_songs(conn: sqlite3.Connection, filters: dict) -> int:
    where, params = _build_where_params(filters)
    sql = f"""
        SELECT COUNT(*) FROM songs s
        LEFT JOIN installed i ON i.song_id = s.id
        WHERE {' AND '.join(where)}
    """
    return conn.execute(sql, params).fetchone()[0]


def mark_installed(conn: sqlite3.Connection, song_id: int,
                   pak_path: str, sig_path: str) -> None:
    conn.execute("DELETE FROM installed WHERE song_id = ?", (song_id,))
    conn.execute(
        "INSERT INTO installed (song_id, pak_path, sig_path, installed_at) VALUES (?,?,?,?)",
        (song_id, pak_path, sig_path, datetime.now().isoformat()),
    )
    conn.commit()


def mark_uninstalled(conn: sqlite3.Connection, song_id: int) -> None:
    conn.execute("DELETE FROM installed WHERE song_id = ?", (song_id,))
    conn.commit()


def get_installed(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT i.*, s.artist, s.title FROM installed i JOIN songs s ON s.id = i.song_id"
    ).fetchall()]


def get_installed_for_song(conn: sqlite3.Connection, song_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT i.*, s.artist, s.title FROM installed i JOIN songs s ON s.id = i.song_id WHERE i.song_id = ?",
        (song_id,)
    ).fetchall()]


def get_setting(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def get_song_by_id(conn: sqlite3.Connection, song_id: int) -> dict | None:
    rows = [dict(r) for r in conn.execute(f"""
        SELECT s.*, {_IS_DEFINITIVE} AS is_definitive,
               i.pak_path, i.sig_path, i.installed_at
        FROM songs s
        LEFT JOIN installed i ON i.song_id = s.id
        WHERE s.id = ?
    """, (song_id,)).fetchall()]
    return rows[0] if rows else None


def get_songs_with_art_url(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT id, art_url FROM songs WHERE art_url IS NOT NULL"
    ).fetchall()]


def update_art_url(conn: sqlite3.Connection, song_id: int, url: str) -> None:
    conn.execute("UPDATE songs SET art_url = ? WHERE id = ?", (url, song_id))
    conn.commit()


def get_or_create_album_art(conn: sqlite3.Connection, artist: str, album: str, art_url: str) -> int:
    # INSERT OR IGNORE: art_url is set once per album and not updated via this path
    conn.execute(
        "INSERT OR IGNORE INTO album_art (artist, album, art_url) VALUES (?, ?, ?)",
        (artist, album, art_url),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM album_art WHERE artist = ? AND album = ?",
        (artist, album),
    ).fetchone()[0]


def get_or_create_album_art_by_url(conn: sqlite3.Connection, artist: str, art_url: str) -> int:
    """Return an album_art id for art_url, reusing any existing record that has that URL.

    Avoids creating per-song duplicates when art_url is the album identifier (e.g.
    scraped MusicBrainz/FSL URLs where the same URL covers multiple tracks).
    """
    existing = conn.execute(
        "SELECT id FROM album_art WHERE art_url = ? LIMIT 1", (art_url,)
    ).fetchone()
    if existing:
        return existing[0]
    # No record for this URL yet — create one, keying album on the URL itself so
    # future calls with the same art_url will hit the early-return above.
    conn.execute(
        "INSERT OR IGNORE INTO album_art (artist, album, art_url) VALUES (?, ?, ?)",
        (artist, art_url, art_url),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM album_art WHERE artist = ? AND album = ?",
        (artist, art_url),
    ).fetchone()[0]


def link_song_album_art(conn: sqlite3.Connection, song_id: int, album_art_id: int) -> None:
    conn.execute("UPDATE songs SET album_art_id = ? WHERE id = ?", (album_art_id, song_id))
    conn.commit()


def get_songs_pending_art(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, artist, title, source FROM songs "
        "WHERE album_art_id IS NULL AND source != 'fusersoundlab'"
    ).fetchall()
    return [dict(r) for r in rows]


def count_pending_art(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM songs WHERE album_art_id IS NULL "
        "AND (source != 'fusersoundlab' OR art_url IS NOT NULL)"
    ).fetchone()[0]
