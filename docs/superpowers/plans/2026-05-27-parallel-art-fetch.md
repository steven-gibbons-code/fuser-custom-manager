# Parallel Art Fetch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the sequential two-step art resolve+download pipeline with a concurrent, visible-window-prioritized pipeline that delivers art to visible rows first and processes the full 10k+ catalog in the background.

**Architecture:** A new `ParallelArtWorker` (QThread) owns a `ThreadPoolExecutor` resolve pool (5 threads, GDrive-first) and a download pool (10 threads). Both pools share an `ArtPriorityQueue` and an internal download queue. `SongTableView` emits visible song IDs on scroll, which `ParallelArtWorker.prioritize()` uses to move those songs to the front of the resolve queue.

**Tech Stack:** PySide6, `concurrent.futures.ThreadPoolExecutor`, `queue.PriorityQueue`, `threading.Lock`, `requests`, SQLite (`check_same_thread=False`)

---

## File Map

| File | Change |
|------|--------|
| `sources/art_resolver.py` | Replace `_throttle` + `_last_call` with thread-safe `_mb_throttle` |
| `gui/workers.py` | Add `_SENTINEL_SONG`, `ArtPriorityQueue`, `ParallelArtWorker`; existing workers untouched |
| `gui/song_table.py` | Add `visibleSongsChanged` signal and `_emit_visible_songs` to `SongTableView`; connect in `set_model` |
| `gui/main_window.py` | Replace `_start_art_resolve` body + delete `_start_art_fetch`; update import; connect `visibleSongsChanged` |
| `tests/test_art_resolver.py` | Add `test_mb_throttle_serializes_calls` |
| `tests/test_workers.py` | Add tests for `ArtPriorityQueue` and `ParallelArtWorker` |

---

## Task 1: Thread-safe MusicBrainz throttle

**Files:**
- Modify: `sources/art_resolver.py`
- Test: `tests/test_art_resolver.py`

The current `_throttle()` uses a bare global `_last_call` with no lock — unsafe when called from multiple threads simultaneously. Replace it with a lock-guarded version.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_art_resolver.py`:

```python
def test_mb_throttle_serializes_calls():
    import threading, time
    from sources.art_resolver import _mb_throttle
    import sources.art_resolver as art_resolver_mod

    # Reset state
    art_resolver_mod._mb_last_call = 0.0

    call_times = []

    def call():
        _mb_throttle()
        call_times.append(time.time())

    threads = [threading.Thread(target=call) for _ in range(3)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    call_times.sort()
    # Each successive call should be at least 0.9s after the previous
    assert call_times[1] - call_times[0] >= 0.9
    assert call_times[2] - call_times[1] >= 0.9
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_art_resolver.py::test_mb_throttle_serializes_calls -v
```

Expected: FAIL (likely `AttributeError: module has no attribute '_mb_throttle'`)

- [ ] **Step 3: Replace throttle in `sources/art_resolver.py`**

Replace lines 1–19 (the imports through `_throttle`) with:

```python
import time
import sqlite3
import threading
import requests

from db import update_art_url
from sources.gdrive_art_index import lookup as gdrive_art_lookup

_MB_URL = "https://musicbrainz.org/ws/2/release"
_CAA_URL = "https://coverartarchive.org/release/{mbid}/front-250"
_USER_AGENT = "FuserCustomTool/1.0 (sgibb.code@gmail.com)"

_mb_lock = threading.Lock()
_mb_last_call = 0.0


def _mb_throttle() -> None:
    """Enforce 1 req/sec globally across all threads for MusicBrainz API calls."""
    global _mb_last_call
    with _mb_lock:
        now = time.time()
        wait = 1.0 - (now - _mb_last_call)
        if wait > 0:
            time.sleep(wait)
        _mb_last_call = time.time()
```

Then in `musicbrainz_lookup`, replace both `_throttle()` calls with `_mb_throttle()`:

```python
def musicbrainz_lookup(artist: str, title: str) -> str | None:
    """Return a Cover Art Archive image URL for the given artist+title, or None."""
    try:
        _mb_throttle()
        resp = requests.get(
            _MB_URL,
            params={"query": f'artist:"{artist}" recording:"{title}"', "fmt": "json", "limit": 5},
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        releases = resp.json().get("releases", [])
        if not releases:
            return None
        mbid = releases[0]["id"]

        _mb_throttle()
        caa_resp = requests.get(
            _CAA_URL.format(mbid=mbid),
            headers={"User-Agent": _USER_AGENT},
            timeout=10,
            allow_redirects=True,
        )
        if caa_resp.status_code == 200:
            return caa_resp.url
        return None
    except Exception:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_art_resolver.py -v
```

Expected: all tests PASS (including the existing `test_musicbrainz_lookup_*` tests)

- [ ] **Step 5: Commit**

```bash
git add sources/art_resolver.py tests/test_art_resolver.py
git commit -m "feat: replace _throttle with thread-safe _mb_throttle in art_resolver"
```

---

## Task 2: ArtPriorityQueue

**Files:**
- Modify: `gui/workers.py`
- Test: `tests/test_workers.py`

A thread-safe priority queue where lower priority number = processed first. Priority 0 = foreground (visible), 1 = background, 999 = sentinel.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_workers.py` (after existing imports, add `ArtPriorityQueue` to the import line later; for now reference the class directly):

```python
def test_art_priority_queue_foreground_before_background():
    from gui.workers import ArtPriorityQueue
    pq = ArtPriorityQueue()
    song_a = {"id": 1, "artist": "A", "title": "X"}
    song_b = {"id": 2, "artist": "B", "title": "Y"}
    pq.put(1, song_a)
    pq.put(1, song_b)
    # Promote song 2 to foreground
    pq.promote([2], {1: song_a, 2: song_b})
    first = pq.get(timeout=0.1)
    assert first is not None and first["id"] == 2


def test_art_priority_queue_claim_prevents_double_processing():
    from gui.workers import ArtPriorityQueue
    pq = ArtPriorityQueue()
    song = {"id": 5, "artist": "A", "title": "X"}
    pq.put(1, song)
    pq.promote([5], {5: song})  # adds duplicate at priority 0
    first = pq.get(timeout=0.1)
    assert first is not None
    assert pq.claim(first["id"]) is True  # first claim succeeds
    second = pq.get(timeout=0.1)
    assert second is not None
    assert pq.claim(second["id"]) is False  # duplicate rejected


def test_art_priority_queue_promote_skips_claimed():
    from gui.workers import ArtPriorityQueue
    pq = ArtPriorityQueue()
    song = {"id": 7, "artist": "A", "title": "X"}
    assert pq.claim(7) is True  # pre-claim (already processing)
    pq.promote([7], {7: song})  # should not add since already claimed
    result = pq.get(timeout=0.1)
    assert result is None  # nothing was added


def test_art_priority_queue_sentinel_terminates_consumer():
    from gui.workers import ArtPriorityQueue, _SENTINEL_SONG
    pq = ArtPriorityQueue()
    song = {"id": 10, "artist": "A", "title": "X"}
    pq.put(1, song)
    pq.put_sentinel()
    first = pq.get(timeout=0.1)
    assert first is not None and first["id"] == 10
    second = pq.get(timeout=0.1)
    assert second is _SENTINEL_SONG
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_workers.py::test_art_priority_queue_foreground_before_background tests/test_workers.py::test_art_priority_queue_claim_prevents_double_processing tests/test_workers.py::test_art_priority_queue_promote_skips_claimed tests/test_workers.py::test_art_priority_queue_sentinel_terminates_consumer -v
```

Expected: FAIL (`ImportError: cannot import name 'ArtPriorityQueue'`)

- [ ] **Step 3: Add `_SENTINEL_SONG` and `ArtPriorityQueue` to `gui/workers.py`**

Add after the existing imports at the top of `gui/workers.py` (before any class definitions):

```python
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
```

Then add the following two definitions before the `RefreshWorker` class:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_workers.py::test_art_priority_queue_foreground_before_background tests/test_workers.py::test_art_priority_queue_claim_prevents_double_processing tests/test_workers.py::test_art_priority_queue_promote_skips_claimed tests/test_workers.py::test_art_priority_queue_sentinel_terminates_consumer -v
```

Expected: all 4 PASS

- [ ] **Step 5: Commit**

```bash
git add gui/workers.py tests/test_workers.py
git commit -m "feat: add ArtPriorityQueue with claim-based deduplication"
```

---

## Task 3: ParallelArtWorker

**Files:**
- Modify: `gui/workers.py`
- Test: `tests/test_workers.py`

The new bulk-fetch QThread. Owns a resolve pool (GDrive-first) and a download pool. Bridges results back to Qt via a result queue polled in `run()`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_workers.py`:

```python
def test_parallel_art_worker_downloads_song_with_existing_url(qtbot, tmp_path):
    import sqlite3
    from gui.workers import ParallelArtWorker

    art_dir = tmp_path / "art"
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            art_url TEXT, source TEXT
        );
        INSERT INTO songs VALUES (2, 'Artist B', 'Song Y', 'http://example.com/2.jpg', 'fucuco');
    """)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"IMAGEDATA"
    received = []

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.requests.get", return_value=mock_resp):
        worker = ParallelArtWorker(conn, n_resolve=1, n_download=1)
        worker.art_ready.connect(lambda sid: received.append(sid))
        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.start()

    assert 2 in received
    assert (art_dir / "2.jpg").read_bytes() == b"IMAGEDATA"


def test_parallel_art_worker_resolves_and_downloads(qtbot, tmp_path):
    import sqlite3
    from gui.workers import ParallelArtWorker

    art_dir = tmp_path / "art"
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            art_url TEXT, source TEXT
        );
        INSERT INTO songs VALUES (1, 'Artist A', 'Song X', NULL, 'fucuco');
    """)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"IMAGEDATA"
    received = []

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.gdrive_art_lookup", return_value="http://gdrive.com/1.jpg"), \
         patch("gui.workers.requests.get", return_value=mock_resp), \
         patch("gui.workers.update_art_url") as mock_update:
        worker = ParallelArtWorker(conn, n_resolve=1, n_download=1)
        worker.art_ready.connect(lambda sid: received.append(sid))
        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.start()

    assert 1 in received
    mock_update.assert_called_once_with(conn, 1, "http://gdrive.com/1.jpg")
    assert (art_dir / "1.jpg").read_bytes() == b"IMAGEDATA"


def test_parallel_art_worker_emits_finished_with_no_pending(qtbot, tmp_path):
    import sqlite3
    from gui.workers import ParallelArtWorker

    art_dir = tmp_path / "art"
    art_dir.mkdir()
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            art_url TEXT, source TEXT
        );
        INSERT INTO songs VALUES (3, 'Artist C', 'Song Z', 'http://example.com/3.jpg', 'fucuco');
    """)
    # Pre-create the image so it's already cached
    (art_dir / "3.jpg").write_bytes(b"CACHED")

    with patch("gui.workers.ART_DIR", art_dir):
        worker = ParallelArtWorker(conn, n_resolve=1, n_download=1)
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()


def test_parallel_art_worker_prioritize_promotes_songs(tmp_path):
    import sqlite3
    from gui.workers import ParallelArtWorker

    art_dir = tmp_path / "art"
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            art_url TEXT, source TEXT
        );
    """)
    for i in range(1, 6):
        conn.execute(
            "INSERT INTO songs VALUES (?, ?, ?, NULL, 'fucuco')",
            (i, f"Artist {i}", f"Song {i}"),
        )
    conn.commit()

    resolve_order = []

    def fake_gdrive(artist):
        resolve_order.append(artist)
        return f"http://example.com/{artist}.jpg"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"IMG"

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.gdrive_art_lookup", side_effect=fake_gdrive), \
         patch("gui.workers.requests.get", return_value=mock_resp), \
         patch("gui.workers.update_art_url"):
        worker = ParallelArtWorker(conn, n_resolve=1, n_download=1)
        # Pre-populate songs_by_id and queue manually for deterministic test
        worker._songs_by_id = {
            i: {"id": i, "artist": f"Artist {i}", "title": f"Song {i}"}
            for i in range(1, 6)
        }
        for i in range(1, 6):
            worker._pq.put(1, worker._songs_by_id[i])
        worker._pq.put_sentinel()
        worker.prioritize([3])  # promote song 3 to foreground
        # Run the resolve loop directly (synchronous)
        # (can't easily run full run() synchronously; check priority queue state)
        first = worker._pq.get(timeout=0.1)
        assert first is not None and first["id"] == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_workers.py::test_parallel_art_worker_downloads_song_with_existing_url tests/test_workers.py::test_parallel_art_worker_resolves_and_downloads tests/test_workers.py::test_parallel_art_worker_emits_finished_with_no_pending tests/test_workers.py::test_parallel_art_worker_prioritize_promotes_songs -v
```

Expected: FAIL (`ImportError: cannot import name 'ParallelArtWorker'`)

- [ ] **Step 3: Add `ParallelArtWorker` to `gui/workers.py`**

Add the following class after `ArtPriorityQueue` and before `RefreshWorker`:

```python
class ParallelArtWorker(QThread):
    """Concurrent art resolve + download worker with visible-window prioritization.

    Resolve pool (GDrive-first, MB fallback) feeds a download pool.
    Call prioritize() with visible song IDs at any time to process those first.
    """

    art_ready = Signal(int)
    finished = Signal()
    status = Signal(str)

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
        self._cancel.set()

    def run(self) -> None:
        ART_DIR.mkdir(parents=True, exist_ok=True)

        rows = self._conn.execute(
            "SELECT id, artist, title FROM songs "
            "WHERE art_url IS NULL AND source != 'fusersoundlab'"
        ).fetchall()
        pending_resolve = [dict(r) for r in rows]

        rows2 = self._conn.execute(
            "SELECT id, art_url FROM songs WHERE art_url IS NOT NULL"
        ).fetchall()
        pending_download = [
            {"id": r["id"], "art_url": r["art_url"]}
            for r in rows2
            if not (ART_DIR / f"{r['id']}.jpg").exists()
        ]

        total = len(pending_resolve) + len(pending_download)
        if total == 0:
            self.finished.emit()
            return

        for s in pending_resolve:
            self._songs_by_id[s["id"]] = s

        for s in pending_resolve:
            self._pq.put(1, s)
        for _ in range(self._n_resolve):
            self._pq.put_sentinel()

        for s in pending_download:
            self._dl_q.put((s["id"], s["art_url"]))

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
                url = gdrive_art_lookup(song["artist"])
                if not url:
                    url = musicbrainz_lookup(song["artist"], song["title"])
                if url:
                    with write_lock:
                        update_art_url(conn, song["id"], url)
                    dl_q.put((song["id"], url))

        def download_loop() -> None:
            while not cancel.is_set():
                try:
                    item = dl_q.get(timeout=0.5)
                except queue.Empty:
                    continue
                if item is None:
                    break
                song_id, url = item
                dest = ART_DIR / f"{song_id}.jpg"
                if dest.exists():
                    result_q.put(song_id)
                    continue
                try:
                    resp = requests.get(
                        url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}
                    )
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
```

Also add `Slot` to the PySide6 import at the top of `gui/workers.py` (line 2):

```python
from PySide6.QtCore import QThread, Signal, Slot
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_workers.py::test_parallel_art_worker_downloads_song_with_existing_url tests/test_workers.py::test_parallel_art_worker_resolves_and_downloads tests/test_workers.py::test_parallel_art_worker_emits_finished_with_no_pending tests/test_workers.py::test_parallel_art_worker_prioritize_promotes_songs -v
```

Expected: all 4 PASS

- [ ] **Step 5: Run the full test suite to check for regressions**

```
pytest tests/test_workers.py -v
```

Expected: all existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add gui/workers.py tests/test_workers.py
git commit -m "feat: add ParallelArtWorker with concurrent resolve+download pools"
```

---

## Task 4: SongTableView visible-songs signal

**Files:**
- Modify: `gui/song_table.py`
- Test: `tests/test_song_table_model.py`

`SongTableView` needs to emit visible song IDs when the user scrolls or the model resets (filter change). The signal connects to `ParallelArtWorker.prioritize`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_song_table_model.py` (or create the file if it only tests the model — add at the bottom):

```python
def test_song_table_view_emits_visible_songs_on_scroll(qtbot):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from PySide6.QtWidgets import QApplication
    from gui.song_table import SongTableModel, SongTableView

    _app = QApplication.instance() or QApplication([])

    model = SongTableModel()
    model.reset([
        {"id": 1, "artist": "A", "title": "X"},
        {"id": 2, "artist": "B", "title": "Y"},
    ])

    view = SongTableView()
    view.set_model(model)
    view.resize(400, 600)
    view.show()
    qtbot.addWidget(view)

    emitted = []
    view.visibleSongsChanged.connect(lambda ids: emitted.extend(ids))

    view.verticalScrollBar().setValue(0)

    assert len(emitted) > 0
    assert all(isinstance(sid, int) for sid in emitted)
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_song_table_model.py::test_song_table_view_emits_visible_songs_on_scroll -v
```

Expected: FAIL (`AttributeError: 'SongTableView' has no attribute 'visibleSongsChanged'`)

- [ ] **Step 3: Add signal and scroll handler to `gui/song_table.py`**

Add `Signal` to the PySide6 import at the top:

```python
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QSize, Signal
```

Add `visibleSongsChanged` signal and `_emit_visible_songs` method to `SongTableView`, and connect them in `set_model`. Replace the full `SongTableView` class with:

```python
class SongTableView(QTableView):
    visibleSongsChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.horizontalHeader().hide()
        self.setWordWrap(False)
        self.setMouseTracking(True)

    def set_model(self, model: SongTableModel):
        from gui.song_delegate import SongRowDelegate, ROW_HEIGHT
        self.setModel(model)
        self.setItemDelegate(SongRowDelegate(self))
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT + 6)
        self.horizontalHeader().setStretchLastSection(True)
        model.modelReset.connect(self._emit_visible_songs)
        self.verticalScrollBar().valueChanged.connect(self._emit_visible_songs)

    def _emit_visible_songs(self) -> None:
        if self.model() is None:
            return
        vp = self.viewport()
        first = self.rowAt(0)
        if first < 0:
            return
        last = self.rowAt(vp.height() - 1)
        if last < 0:
            last = self.model().rowCount() - 1
        song_ids = []
        for row in range(first, last + 1):
            idx = self.model().index(row, 0)
            song = idx.data(Qt.ItemDataRole.UserRole)
            if song and "id" in song:
                song_ids.append(song["id"])
        if song_ids:
            self.visibleSongsChanged.emit(song_ids)

    def get_selected_songs(self) -> list[dict]:
        if self.model() is None:
            return []
        return [
            idx.data(Qt.ItemDataRole.UserRole)
            for idx in self.selectionModel().selectedRows()
        ]

    def select_all(self):
        self.selectAll()

    def deselect_all(self):
        self.clearSelection()

    def set_batch_mode(self, enabled: bool):
        if enabled:
            self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        else:
            self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_song_table_model.py::test_song_table_view_emits_visible_songs_on_scroll -v
```

Expected: PASS

- [ ] **Step 5: Run full model test suite**

```
pytest tests/test_song_table_model.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add gui/song_table.py tests/test_song_table_model.py
git commit -m "feat: add visibleSongsChanged signal to SongTableView"
```

---

## Task 5: MainWindow wiring

**Files:**
- Modify: `gui/main_window.py`
- Test: `tests/test_main_window_layout.py` (smoke — verify no crash on startup)

Replace the two-step `_start_art_resolve` + `_start_art_fetch` with a single method using `ParallelArtWorker`. Connect `visibleSongsChanged` to `prioritize` while the worker runs.

- [ ] **Step 1: Run the existing smoke test to establish a baseline**

```
pytest tests/test_main_window_layout.py tests/test_gui_smoke.py -v
```

Expected: all PASS (baseline before changes)

- [ ] **Step 2: Update imports in `gui/main_window.py`**

Replace line 19:

```python
from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker, ArtFetchWorker, ArtResolveWorker, SingleArtWorker
```

with:

```python
from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker, ParallelArtWorker, SingleArtWorker
```

- [ ] **Step 3: Replace `_start_art_resolve` and delete `_start_art_fetch` in `gui/main_window.py`**

Replace the existing `_start_art_resolve` method:

```python
    def _start_art_resolve(self):
        self._set_action_buttons_enabled(False)
        worker = ArtResolveWorker(self.conn)
        worker.status.connect(self.status_bar.set_message)
        worker.error.connect(self.status_bar.set_error)
        worker.error.connect(lambda _: self._set_action_buttons_enabled(True))
        worker.finished.connect(self._start_art_fetch)
        self._art_worker = worker
        worker.start()
```

with:

```python
    def _start_art_resolve(self):
        self._set_action_buttons_enabled(False)
        worker = ParallelArtWorker(self.conn)
        worker.status.connect(self.status_bar.set_message)
        worker.art_ready.connect(self._on_art_ready)
        worker.finished.connect(self.status_bar.set_idle)
        worker.finished.connect(lambda: self._set_action_buttons_enabled(True))
        self.song_table.visibleSongsChanged.connect(worker.prioritize)
        worker.finished.connect(
            lambda: self.song_table.visibleSongsChanged.disconnect(worker.prioritize)
        )
        self._art_worker = worker
        worker.start()
        self.song_table._emit_visible_songs()
```

Then delete the entire `_start_art_fetch` method (lines 280–293 in the original):

```python
    def _start_art_fetch(self):
        songs = get_songs_with_art_url(self.conn)
        uncached = [s for s in songs if not (ART_DIR / f"{s['id']}.jpg").exists()]
        if not uncached:
            self._set_action_buttons_enabled(True)
            self.status_bar.set_idle()
            return
        worker = ArtFetchWorker(uncached)
        worker.status.connect(self.status_bar.set_message)
        worker.art_ready.connect(self._on_art_ready)
        worker.finished.connect(self.status_bar.set_idle)
        worker.finished.connect(lambda: self._set_action_buttons_enabled(True))
        self._art_worker = worker
        worker.start()
```

Also remove unused imports from `main_window.py` — `get_songs_with_art_url` and `count_pending_art` are no longer needed if `_start_art_fetch` is gone. Check line 12 and remove unused names:

```python
from db import init_db, get_songs, get_song_by_id, get_setting, set_setting, ART_DIR, count_pending_art
```

(`get_songs_with_art_url` removed; `count_pending_art` still used in `_start_refresh` — keep it)

- [ ] **Step 4: Run smoke tests to verify no regressions**

```
pytest tests/test_main_window_layout.py tests/test_gui_smoke.py -v
```

Expected: all PASS

- [ ] **Step 5: Run the full test suite**

```
pytest -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add gui/main_window.py
git commit -m "feat: wire ParallelArtWorker into MainWindow, connect visibleSongsChanged"
```

---

## Self-Review

**Spec coverage check:**
- ✅ GDrive-first, MB fallback — Task 3 `resolve_loop`
- ✅ Priority queue, foreground/background — Task 2 `ArtPriorityQueue`
- ✅ Resolve pool 3–5 threads — `n_resolve=5` default in `ParallelArtWorker.__init__`
- ✅ Download pool 8–10 threads — `n_download=10` default
- ✅ Visible-window signal from `SongTableView` — Task 4
- ✅ `prioritize` slot connected in MainWindow — Task 5
- ✅ Initial visible songs emitted on worker start — `_emit_visible_songs()` called in Task 5
- ✅ DB write lock — `self._write_lock` in `resolve_loop`
- ✅ Cancel support — `self._cancel` threading.Event, checked in loops
- ✅ `SingleArtWorker` unchanged — not touched
- ✅ Existing workers (`ArtResolveWorker`, `ArtFetchWorker`) kept for test compatibility
- ✅ No DB schema changes
- ✅ `art_ready` signal → pixmap cache clear + viewport repaint (existing `_on_art_ready` wired in Task 5)

**Placeholder scan:** No TBDs, no "similar to Task N" shortcuts, all code blocks complete.

**Type consistency:** `ArtPriorityQueue` API (`put`, `put_sentinel`, `promote`, `claim`, `get`, `empty`) consistent across Task 2 definition and Task 3 usage. `_SENTINEL_SONG` defined once, referenced by identity (`is`) in Task 3 loops. `visibleSongsChanged = Signal(list)` matches `@Slot(list)` on `prioritize`.
