from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QThread, Signal, Slot
import requests
import queue
import threading

from db import upsert_songs, ART_DIR, get_or_create_album_art, link_song_album_art
from downloader import download
from installer import install_pairs
from sources.fucuco import fetch_all as fetch_fucuco
from sources.fusersoundlab import fetch_all as fetch_fsl
from sources.art_resolver import bulk_resolve, itunes_lookup
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


class ParallelArtWorker(QThread):
    """Concurrent art resolve + download worker with visible-window prioritization.

    Resolve pool (iTunes-first, GDrive fallback) feeds a download pool.
    Call prioritize() with visible song IDs at any time to process those first.
    """

    art_ready = Signal(int)
    finished = Signal()
    status = Signal(str)
    progress = Signal(float)

    def __init__(self, conn, n_resolve: int = 5, n_download: int = 10, parent=None):
        super().__init__(parent)
        self._conn = conn
        self._n_resolve = n_resolve
        self._n_download = n_download
        self._cancel = threading.Event()
        self._pq = ArtPriorityQueue()
        self._dl_q: queue.Queue = queue.Queue()
        self._songs_by_id: dict[int, dict] = {}
        self._write_lock = threading.Lock()

    @Slot(list)
    def prioritize(self, song_ids: list) -> None:
        self._pq.promote(song_ids, self._songs_by_id)

    def stop(self) -> None:
        # In-flight network calls (up to 15s) must complete before the thread exits.
        self._cancel.set()

    def run(self) -> None:
        ART_DIR.mkdir(parents=True, exist_ok=True)
        self.status.emit("Resolving art…")

        conn = self._conn

        # Any song that already has art_url (FSL poster field, fucuco scraped URLs, etc.)
        # doesn't need an iTunes lookup — create album_art records and link them now so
        # they fall into the normal pending_download path below.
        direct_rows = conn.execute(
            "SELECT id, artist, title, art_url FROM songs "
            "WHERE album_art_id IS NULL AND art_url IS NOT NULL"
        ).fetchall()
        for r in direct_rows:
            if self._cancel.is_set():
                self.finished.emit()
                return
            art_id = get_or_create_album_art(conn, r["artist"], r["title"], r["art_url"])
            link_song_album_art(conn, r["id"], art_id)

        rows = conn.execute(
            "SELECT id, artist, title FROM songs "
            "WHERE album_art_id IS NULL AND art_url IS NULL AND source != 'fusersoundlab'"
        ).fetchall()
        pending_resolve = [dict(r) for r in rows]

        rows2 = conn.execute(
            "SELECT s.id, s.album_art_id, a.art_url FROM songs s "
            "JOIN album_art a ON a.id = s.album_art_id "
            "WHERE s.album_art_id IS NOT NULL"
        ).fetchall()
        pending_download = [
            {"id": r["id"], "album_art_id": r["album_art_id"], "art_url": r["art_url"]}
            for r in rows2
        ]

        if not pending_resolve and not pending_download:
            self.finished.emit()
            return

        total = len(pending_resolve) + len(pending_download)

        for s in pending_resolve:
            self._songs_by_id[s["id"]] = s

        for s in pending_resolve:
            self._pq.put(1, s)
        for _ in range(self._n_resolve):
            self._pq.put_sentinel()

        for s in pending_download:
            self._dl_q.put((s["id"], s["album_art_id"], s["art_url"]))

        result_q: queue.Queue = queue.Queue()
        completed = [0]
        sentinels_sent = [False]

        cancel = self._cancel
        pq = self._pq
        dl_q = self._dl_q
        write_lock = self._write_lock
        conn = self._conn

        def resolve_loop() -> None:
            while not cancel.is_set():
                song = pq.get(timeout=0.5)
                if song is None:
                    continue
                if song is _SENTINEL_SONG:
                    break
                if not pq.claim(song["id"]):
                    continue
                itunes_result = itunes_lookup(song["artist"], song["title"])
                if itunes_result:
                    album_name, art_url = itunes_result
                else:
                    gdrive_url = gdrive_art_lookup(song["artist"])
                    if gdrive_url:
                        album_name, art_url = "__artist__", gdrive_url
                    else:
                        result_q.put(song["id"])
                        continue
                with write_lock:
                    album_art_id = get_or_create_album_art(conn, song["artist"], album_name, art_url)
                    link_song_album_art(conn, song["id"], album_art_id)
                dest = ART_DIR / f"{album_art_id}.jpg"
                if dest.exists():
                    result_q.put(song["id"])
                else:
                    dl_q.put((song["id"], album_art_id, art_url))

        def download_loop() -> None:
            while not cancel.is_set():
                try:
                    item = dl_q.get(timeout=0.5)
                except queue.Empty:
                    continue
                if item is None:
                    break
                song_id, album_art_id, url = item
                dest = ART_DIR / f"{album_art_id}.jpg"
                if dest.exists():
                    result_q.put(song_id)
                    continue
                try:
                    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200:
                        dest.write_bytes(resp.content)
                        result_q.put(song_id)
                except Exception:
                    pass

        with ThreadPoolExecutor(max_workers=self._n_resolve) as rpool, \
             ThreadPoolExecutor(max_workers=self._n_download) as dpool:

            resolve_futs = [rpool.submit(resolve_loop) for _ in range(self._n_resolve)]
            download_futs = [dpool.submit(download_loop) for _ in range(self._n_download)]

            while not self._cancel.is_set():
                try:
                    song_id = result_q.get(timeout=0.1)
                    completed[0] += 1
                    self.art_ready.emit(song_id)
                    progress_val = min(completed[0] / total, 1.0) if total else 1.0
                    self.progress.emit(progress_val)
                    self.status.emit(f"Fetching art… ({completed[0]}/{total})")
                except queue.Empty:
                    pass

                if not sentinels_sent[0] and all(f.done() for f in resolve_futs):
                    for _ in range(self._n_download):
                        self._dl_q.put(None)
                    sentinels_sent[0] = True

                if sentinels_sent[0] and all(f.done() for f in download_futs):
                    break

        while not result_q.empty():
            song_id = result_q.get_nowait()
            completed[0] += 1
            self.art_ready.emit(song_id)

        self.finished.emit()


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
            album_art_id = self._song.get("album_art_id")
            art_url = None

            if album_art_id is None:
                self.status.emit("Looking up art… (1/1)")
                itunes_result = itunes_lookup(self._song["artist"], self._song["title"])
                if itunes_result:
                    album_name, art_url = itunes_result
                else:
                    gdrive_url = gdrive_art_lookup(
                        self._song["artist"], status_cb=self.status.emit
                    )
                    if gdrive_url:
                        album_name, art_url = "__artist__", gdrive_url
                    else:
                        self.finished.emit(song_id)
                        return

                album_art_id = get_or_create_album_art(
                    self._conn, self._song["artist"], album_name, art_url
                )
                link_song_album_art(self._conn, song_id, album_art_id)

            dest = ART_DIR / f"{album_art_id}.jpg"
            if not dest.exists():
                self.status.emit("Downloading art…")
                ART_DIR.mkdir(parents=True, exist_ok=True)
                if art_url is None:
                    art_url = self._conn.execute(
                        "SELECT art_url FROM album_art WHERE id = ?", (album_art_id,)
                    ).fetchone()[0]
                resp = requests.get(
                    art_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}
                )
                if resp.status_code == 200:
                    dest.write_bytes(resp.content)

            self.finished.emit(song_id)
        except Exception as exc:
            self.error.emit(str(exc) or type(exc).__name__)
