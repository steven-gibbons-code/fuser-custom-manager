import re
import shutil
import sqlite3
from pathlib import Path

from db import mark_installed, mark_uninstalled, get_installed, get_songs, get_installed_for_song
from downloader import DownloadResult

INSTALL_DIR = Path(r"C:\Fuser\Fuser\Content\Paks\custom_songs")
_ILLEGAL = re.compile(r'[<>:"/\\|?*]')


def sanitise_artist(name: str) -> str:
    return " ".join(_ILLEGAL.sub("", name).split())


def install_pairs(result: DownloadResult, song_id: int, artist: str,
                  install_root: Path, conn: sqlite3.Connection) -> None:
    if len(result.pairs) > 1:
        # DB schema supports one installed record per song_id.
        # Multi-song folder downloads are not yet supported — install first pair only.
        pairs_to_install = result.pairs[:1]
    else:
        pairs_to_install = result.pairs
    artist_dir = install_root / sanitise_artist(artist)
    artist_dir.mkdir(parents=True, exist_ok=True)
    for pak_src, sig_src in pairs_to_install:
        pak_dst = artist_dir / pak_src.name
        shutil.move(str(pak_src), str(pak_dst))
        sig_dst = ""
        if sig_src and sig_src.exists():
            sig_dst_path = artist_dir / sig_src.name
            shutil.move(str(sig_src), str(sig_dst_path))
            sig_dst = str(sig_dst_path)
        mark_installed(conn, song_id, str(pak_dst), sig_dst)
    # Clean up staging work_dir if present
    if result.work_dir and result.work_dir.exists():
        shutil.rmtree(result.work_dir, ignore_errors=True)


def uninstall(song_id: int, install_root: Path, conn: sqlite3.Connection) -> None:
    for rec in get_installed_for_song(conn, song_id):
        for key in ("pak_path", "sig_path"):
            p = Path(rec[key]) if rec.get(key) else None
            if p and p.exists():
                p.unlink()
        pak_path = rec.get("pak_path")
        if pak_path:
            artist_dir = Path(pak_path).parent
            if artist_dir.exists() and not any(artist_dir.iterdir()):
                artist_dir.rmdir()
    mark_uninstalled(conn, song_id)


def scan_and_sync(install_root: Path, conn: sqlite3.Connection) -> None:
    if not install_root.exists():
        return
    index = {
        (s["artist"].lower(), s["title"].lower()): s["id"]
        for s in get_songs(conn, {})
    }
    for pak in install_root.rglob("*.pak"):
        sig = pak.with_suffix(".sig")
        key = (pak.parent.name.lower(), pak.stem.lower())
        if (song_id := index.get(key)):
            mark_installed(conn, song_id, str(pak), str(sig) if sig.exists() else "")
