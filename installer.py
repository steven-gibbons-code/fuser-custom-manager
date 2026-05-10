import shutil
import sqlite3
from pathlib import Path

from db import mark_installed, mark_uninstalled, get_installed, get_songs
from downloader import DownloadResult

DEFAULT_INSTALL_DIR = Path(r"C:\Fuser\Fuser\Content\Paks\custom_songs")


import re

def sanitise_artist(name: str) -> str:
    return " ".join(re.sub(r'[<>:"/\\|?*]', "", name).split())


def install_pairs(result: DownloadResult, song_id: int, artist: str,
                  install_root: Path, conn: sqlite3.Connection) -> None:
    artist_dir = install_root / sanitise_artist(artist)
    artist_dir.mkdir(parents=True, exist_ok=True)
    for pak_src, sig_src in result.pairs:
        pak_dst = artist_dir / pak_src.name
        shutil.move(str(pak_src), str(pak_dst))
        sig_dst = ""
        if sig_src and sig_src.exists():
            sig_dst_path = artist_dir / sig_src.name
            shutil.move(str(sig_src), str(sig_dst_path))
            sig_dst = str(sig_dst_path)
        mark_installed(conn, song_id, str(pak_dst), sig_dst)


def install_manual_files(song_id: int, artist: str, pak_path: Path, sig_path: Path | None,
                         install_root: Path, conn: sqlite3.Connection) -> None:
    """Copy user-selected .pak/.sig files into the install directory and mark installed.

    Unlike install_pairs (which MOVES files from a staging temp dir), this
    COPIES the files so the user's original download location is preserved.
    """
    artist_dir = install_root / sanitise_artist(artist)
    artist_dir.mkdir(parents=True, exist_ok=True)

    pak_dst = artist_dir / pak_path.name
    shutil.copy2(str(pak_path), str(pak_dst))

    sig_dst = ""
    if sig_path and sig_path.exists():
        sig_dst_path = artist_dir / sig_path.name
        shutil.copy2(str(sig_path), str(sig_dst_path))
        sig_dst = str(sig_dst_path)

    mark_installed(conn, song_id, str(pak_dst), sig_dst)


def uninstall(song_id: int, install_root: Path, conn: sqlite3.Connection) -> None:
    for rec in get_installed(conn):
        if rec["song_id"] != song_id:
            continue
        for key in ("pak_path", "sig_path"):
            p = Path(rec[key]) if rec.get(key) else None
            if p and p.exists():
                p.unlink()
        artist_dir = Path(rec["pak_path"]).parent
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