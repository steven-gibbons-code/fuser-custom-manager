from pathlib import Path
from PySide6.QtCore import QThread, Signal
import requests
import queue
import threading

from db import upsert_songs, ART_DIR, update_art_url
from downloader import download
from installer import install_pairs
from sources.fucuco import fetch_all as fetch_fucuco
from sources.fusersoundlab import fetch_all as fetch_fsl
from sources.art_resolver import bulk_resolve, musicbrainz_lookup
from sources.gdrive_art_index import lookup as gdrive_art_lookup


_SENTINEL_SONG: dict = {"id": -1, "_sentinel": True}


class ArtPriorityQueue:
    """Thread-safe priority queue for art resolution tasks.

    Priority 0 = foreground (visible rows), 1 = background, 999 = sentinel.
    Use claim() instead of a separate is_done check — it atomically marks
    and returns whether this thread won the race.
    """

    def __init__(self) -> None:
        self._q: queue.PriorityQueue = queue.PriorityQueue()
        self._claimed: set[int] = set()
        self._lock = threading.Lock()
        self._counter = 0

    def put(self, priority: int, song: dict) -> None:
        with self._lock:
            if song["id"] not in self._claimed:
                self._counter += 1
                self._q.put((priority, self._counter, song))

    def put_sentinel(self) -> None:
        """Enqueue a sentinel that terminates one consumer when dequeued."""
        with self._lock:
            self._counter += 1
            self._q.put((999, self._counter, _SENTINEL_SONG))

    def promote(self, song_ids: list[int], songs_by_id: dict) -> None:
        """Re-enqueue listed songs at priority 0. Skips already-claimed songs."""
        with self._lock:
            for sid in song_ids:
                if sid not in self._claimed:
                    song = songs_by_id.get(sid)
                    if song:
                        self._counter += 1
                        self._q.put((0, self._counter, song))

    def claim(self, song_id: int) -> bool:
        """Atomically mark song as claimed. Returns True if this call won the race."""
        with self._lock:
            if song_id in self._claimed:
                return False
            self._claimed.add(song_id)
            return True

    def get(self, timeout: float = 0.5) -> dict | None:
        """Return next song dict (may be _SENTINEL_SONG), or None on timeout."""
        try:
            _, _, item = self._q.get(timeout=timeout)
            return item
        except queue.Empty:
            return None

    def empty(self) -> bool:
        return self._q.empty()


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


class ArtResolveWorker(QThread):
    finished = Signal()
    error = Signal(str)
    status = Signal(str)

    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self._conn = conn

    def run(self):
        try:
            bulk_resolve(self._conn, progress_cb=self.status.emit)
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc) or type(exc).__name__)


class SingleArtWorker(QThread):
    finished = Signal(int)
    error = Signal(str)
    status = Signal(str)

    def __init__(self, song: dict, conn, parent=None):
        super().__init__(parent)
        self._song = song
        self._conn = conn

    def run(self):
        try:
            song_id = self._song["id"]
            art_url = self._song.get("art_url")

            if art_url is None:
                self.status.emit("Looking up art…")
                art_url = musicbrainz_lookup(self._song["artist"], self._song["title"])
                if not art_url:
                    art_url = gdrive_art_lookup(
                        self._song["artist"], status_cb=self.status.emit
                    )
                if art_url:
                    update_art_url(self._conn, song_id, art_url)

            if art_url:
                dest = ART_DIR / f"{song_id}.jpg"
                if not dest.exists():
                    self.status.emit("Downloading art…")
                    ART_DIR.mkdir(parents=True, exist_ok=True)
                    resp = requests.get(
                        art_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}
                    )
                    if resp.status_code == 200:
                        dest.write_bytes(resp.content)

            self.finished.emit(song_id)
        except Exception as exc:
            self.error.emit(str(exc) or type(exc).__name__)
