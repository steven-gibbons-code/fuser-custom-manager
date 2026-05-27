from pathlib import Path
from PySide6.QtCore import QThread, Signal
import requests

from db import upsert_songs, ART_DIR
from downloader import download
from installer import install_pairs
from sources.fucuco import fetch_all as fetch_fucuco
from sources.fusersoundlab import fetch_all as fetch_fsl
from sources.art_resolver import bulk_resolve


class RefreshWorker(QThread):
    finished = Signal()
    error = Signal(str)
    status = Signal(str)

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn

    def run(self):
        try:
            self.status.emit("Refreshing sources…")
            songs = fetch_fucuco() + fetch_fsl()
            upsert_songs(self._conn, songs)
            bulk_resolve(self._conn, progress_cb=self.status.emit)
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc) or type(exc).__name__)


class DownloadWorker(QThread):
    progress = Signal(float)
    done = Signal(str)
    manual = Signal(str)
    error = Signal(str)

    def __init__(self, song: dict, install_dir: Path, conn, parent=None):
        super().__init__(parent)
        self._song = song
        self._install_dir = install_dir
        self._conn = conn

    def run(self):
        try:
            result = download(
                self._song["link"],
                progress_cb=lambda p: self.progress.emit(p),
            )
            if result.status == "ok":
                try:
                    install_pairs(result, self._song["id"], self._song["artist"],
                                  self._install_dir, self._conn)
                    self.done.emit(self._song["title"])
                except Exception as exc:
                    self.error.emit(str(exc) or "Install failed")
            elif result.status == "manual":
                self.manual.emit(result.raw_url or "")
            else:
                self.error.emit(result.error_msg or "Unknown error")
        except Exception as exc:
            self.error.emit(str(exc) or type(exc).__name__)


class BatchDownloadWorker(QThread):
    item_progress = Signal(str)
    finished = Signal(list)

    def __init__(self, songs: list[dict], install_dir: Path, conn, parent=None):
        super().__init__(parent)
        self._songs = songs
        self._install_dir = install_dir
        self._conn = conn

    def run(self):
        results: list[dict] = []
        n = len(self._songs)
        for i, song in enumerate(self._songs):
            self.item_progress.emit(f"[{i + 1}/{n}] Downloading: {song['title']}")
            result = download(song["link"])
            entry: dict = {"song": song}
            if result.status == "ok":
                try:
                    install_pairs(result, song["id"], song["artist"],
                                  self._install_dir, self._conn)
                    entry["status"] = "ok"
                    entry["message"] = "Installed"
                except Exception as exc:
                    entry["status"] = "error"
                    entry["message"] = str(exc) or "Install failed"
            elif result.status == "manual":
                entry["status"] = "manual"
                entry["message"] = "Manual download required"
            else:
                entry["status"] = "error"
                entry["message"] = result.error_msg or "Unknown error"
            results.append(entry)
        self.finished.emit(results)


class ArtFetchWorker(QThread):
    art_ready = Signal(int)
    finished = Signal()
    status = Signal(str)

    def __init__(self, songs: list[dict], parent=None):
        super().__init__(parent)
        self._songs = songs  # each dict has {id, art_url}

    def run(self):
        ART_DIR.mkdir(parents=True, exist_ok=True)
        total = len(self._songs)
        failed = 0
        for i, song in enumerate(self._songs):
            song_id = song["id"]
            dest = ART_DIR / f"{song_id}.jpg"
            if dest.exists():
                continue
            self.status.emit(f"Fetching art… ({i + 1}/{total})")
            try:
                resp = requests.get(
                    song["art_url"],
                    timeout=15,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                if resp.status_code == 200:
                    dest.write_bytes(resp.content)
                    self.art_ready.emit(song_id)
                else:
                    failed += 1
            except Exception:
                failed += 1
        if failed:
            self.status.emit(f"Art fetch done — {total - failed}/{total} downloaded")
        self.finished.emit()
