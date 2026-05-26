from pathlib import Path
from PySide6.QtCore import QThread, Signal

from db import upsert_songs
from downloader import download
from installer import install_pairs
from sources.fucuco import fetch_all as fetch_fucuco
from sources.fusersoundlab import fetch_all as fetch_fsl


class RefreshWorker(QThread):
    finished = Signal()
    error = Signal(str)

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn

    def run(self):
        try:
            songs = fetch_fucuco() + fetch_fsl()
            upsert_songs(self._conn, songs)
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
