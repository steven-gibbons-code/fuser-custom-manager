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
    UNIQUE(source, artist, title)
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


def init_db(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def upsert_songs(conn: sqlite3.Connection, songs: list[dict]) -> None:
    conn.executemany("""
        INSERT INTO songs (source, artist, title, creator, genre, year, bpm, key,
                           de_status, complete, complete_notes, stream_opt, origin,
                           link, link_host, last_seen)
        VALUES (:source, :artist, :title, :creator, :genre, :year, :bpm, :key,
                :de_status, :complete, :complete_notes, :stream_opt, :origin,
                :link, :link_host, :last_seen)
        ON CONFLICT(source, artist, title) DO UPDATE SET
            creator=excluded.creator, genre=excluded.genre, year=excluded.year,
            bpm=excluded.bpm, key=excluded.key, de_status=excluded.de_status,
            complete=excluded.complete, complete_notes=excluded.complete_notes,
            stream_opt=excluded.stream_opt, origin=excluded.origin,
            link=excluded.link, link_host=excluded.link_host,
            last_seen=excluded.last_seen
    """, songs)
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
    if filters.get("definitive_only"):
        where.append(f"({_IS_DEFINITIVE}) = 1")
    if filters.get("bpm_min") is not None:
        where.append("s.bpm >= ?")
        params.append(filters["bpm_min"])
    if filters.get("bpm_max") is not None:
        where.append("s.bpm <= ?")
        params.append(filters["bpm_max"])

    _ALLOWED_ORDER = {
        "s.artist", "s.title", "s.creator", "s.bpm", "s.year",
        "s.genre", "s.key", "s.source", "s.de_status",
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
