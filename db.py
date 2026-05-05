import sqlite3
from datetime import datetime
from pathlib import Path

DB_DIR = Path.home() / ".fuser_manager"
DB_PATH = DB_DIR / "catalog.db"

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
    UNIQUE(source, link)
);

CREATE TABLE IF NOT EXISTS installed (
    id           INTEGER PRIMARY KEY,
    song_id      INTEGER UNIQUE REFERENCES songs(id) ON DELETE CASCADE,
    pak_path     TEXT NOT NULL,
    sig_path     TEXT,
    installed_at TEXT NOT NULL
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


def _migrate_add_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(songs)").fetchall()}
    new_cols = [
        ("disc1",         "TEXT"),
        ("disc2",         "TEXT"),
        ("disc3",         "TEXT"),
        ("disc4",         "TEXT"),
        ("download_type", "TEXT"),
        ("quality",       "TEXT"),
    ]
    for col_name, col_type in new_cols:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE songs ADD COLUMN {col_name} {col_type}")
    conn.commit()


def _needs_migration(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='songs'"
    ).fetchone()
    if not row:
        return False
    # Old schema used UNIQUE(source, artist, title); new uses UNIQUE(source, link)
    return "artist, title" in row[0].lower()


def init_db(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    if _needs_migration(conn):
        conn.executescript("DROP TABLE IF EXISTS installed; DROP TABLE IF EXISTS songs;")
    conn.executescript(SCHEMA)
    _migrate_add_columns(conn)
    conn.commit()
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
        s["quality"] = derive_quality(s)
        enriched.append(s)
    conn.executemany("""
        INSERT INTO songs (source, artist, title, creator, genre, year, bpm, key,
                           de_status, complete, complete_notes, stream_opt, origin,
                           link, link_host, last_seen,
                           disc1, disc2, disc3, disc4, download_type, quality)
        VALUES (:source, :artist, :title, :creator, :genre, :year, :bpm, :key,
                :de_status, :complete, :complete_notes, :stream_opt, :origin,
                :link, :link_host, :last_seen,
                :disc1, :disc2, :disc3, :disc4, :download_type, :quality)
        ON CONFLICT(source, link) DO UPDATE SET
            artist=excluded.artist, title=excluded.title,
            creator=excluded.creator, genre=excluded.genre, year=excluded.year,
            bpm=excluded.bpm, key=excluded.key, de_status=excluded.de_status,
            complete=excluded.complete, complete_notes=excluded.complete_notes,
            stream_opt=excluded.stream_opt, origin=excluded.origin,
            link_host=excluded.link_host, last_seen=excluded.last_seen,
            disc1=excluded.disc1, disc2=excluded.disc2,
            disc3=excluded.disc3, disc4=excluded.disc4,
            download_type=excluded.download_type, quality=excluded.quality
    """, enriched)
    conn.commit()


def get_songs(conn: sqlite3.Connection, filters: dict) -> list[dict]:
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
        # Legacy support — kept for backwards compat with existing filter dicts
        where.append("s.quality IN ('Definitive', 'Official')")
    if filters.get("bpm_min") is not None:
        where.append("s.bpm >= ?")
        params.append(filters["bpm_min"])
    if filters.get("bpm_max") is not None:
        where.append("s.bpm <= ?")
        params.append(filters["bpm_max"])

    _ALLOWED_ORDER = {
        "s.artist", "s.title", "s.creator", "s.bpm", "s.year",
        "s.genre", "s.key", "s.source", "s.de_status", "s.quality",
    }
    order = filters.get("order_by", "s.artist")
    if order not in _ALLOWED_ORDER:
        order = "s.artist"
    direction = "DESC" if filters.get("descending") else "ASC"
    offset = filters.get("offset", 0)

    sql = f"""
        SELECT s.*, {_IS_DEFINITIVE} AS is_definitive,
               i.pak_path, i.sig_path, i.installed_at
        FROM songs s
        LEFT JOIN installed i ON i.song_id = s.id
        WHERE {' AND '.join(where)}
        ORDER BY {order} {direction}
        LIMIT 100 OFFSET ?
    """
    params.append(offset)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


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


def get_song_by_id(conn: sqlite3.Connection, song_id: int) -> dict | None:
    rows = [dict(r) for r in conn.execute(f"""
        SELECT s.*, {_IS_DEFINITIVE} AS is_definitive,
               i.pak_path, i.sig_path, i.installed_at
        FROM songs s
        LEFT JOIN installed i ON i.song_id = s.id
        WHERE s.id = ?
    """, (song_id,)).fetchall()]
    return rows[0] if rows else None
