import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication
from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker, ArtFetchWorker, ArtResolveWorker, SingleArtWorker

_app = QApplication.instance() or QApplication([])


def test_refresh_worker_emits_finished(qtbot, tmp_path):
    conn = MagicMock()
    worker = RefreshWorker(conn)
    mock_songs = [{"title": "A"}, {"title": "B"}]
    with patch("gui.workers.fetch_fucuco", return_value=[mock_songs[0]]), \
         patch("gui.workers.fetch_fsl", return_value=[mock_songs[1]]), \
         patch("gui.workers.upsert_songs") as mock_upsert, \
         patch("gui.workers.bulk_resolve") as mock_resolve:
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()
        mock_upsert.assert_called_once()
        mock_resolve.assert_not_called()


def test_refresh_worker_emits_error_on_exception(qtbot):
    conn = MagicMock()
    worker = RefreshWorker(conn)
    with patch("gui.workers.fetch_fucuco", side_effect=RuntimeError("network error")):
        with qtbot.waitSignal(worker.error, timeout=3000) as blocker:
            worker.start()
    assert "network error" in blocker.args[0]


def test_download_worker_emits_done_on_ok_status(qtbot):
    conn = MagicMock()
    song = {"id": 1, "title": "Get Lucky", "link": "http://example.com/song",
            "artist": "Daft Punk"}
    install_dir = Path("/fake/dir")
    mock_result = MagicMock()
    mock_result.status = "ok"

    progress_values = []

    with patch("gui.workers.download", return_value=mock_result) as mock_dl, \
         patch("gui.workers.install_pairs"):
        worker = DownloadWorker(song, install_dir, conn)
        worker.progress.connect(lambda v: progress_values.append(v))
        with qtbot.waitSignal(worker.done, timeout=3000):
            worker.start()


def test_download_worker_emits_manual_on_manual_status(qtbot):
    conn = MagicMock()
    song = {"id": 1, "title": "Get Lucky", "link": "http://example.com", "artist": "Daft Punk"}
    mock_result = MagicMock()
    mock_result.status = "manual"
    mock_result.raw_url = "http://example.com/manual"

    with patch("gui.workers.download", return_value=mock_result):
        worker = DownloadWorker(song, Path("/fake"), conn)
        with qtbot.waitSignal(worker.manual, timeout=3000) as blocker:
            worker.start()
    assert blocker.args[0] == "http://example.com/manual"


def test_download_worker_emits_error_on_error_status(qtbot):
    conn = MagicMock()
    song = {"id": 1, "title": "Get Lucky", "link": "http://example.com", "artist": "Daft Punk"}
    mock_result = MagicMock()
    mock_result.status = "error"
    mock_result.error_msg = "404 not found"

    with patch("gui.workers.download", return_value=mock_result):
        worker = DownloadWorker(song, Path("/fake"), conn)
        with qtbot.waitSignal(worker.error, timeout=3000) as blocker:
            worker.start()
    assert "404" in blocker.args[0]


def test_batch_worker_emits_finished_with_results(qtbot):
    conn = MagicMock()
    songs = [
        {"id": 1, "title": "A", "link": "http://a.com", "artist": "ArtA"},
        {"id": 2, "title": "B", "link": "http://b.com", "artist": "ArtB"},
    ]
    mock_result = MagicMock()
    mock_result.status = "ok"

    with patch("gui.workers.download", return_value=mock_result), \
         patch("gui.workers.install_pairs"):
        worker = BatchDownloadWorker(songs, Path("/fake"), conn)
        with qtbot.waitSignal(worker.finished, timeout=5000) as blocker:
            worker.start()
    results = blocker.args[0]
    assert len(results) == 2
    assert all(r["status"] == "ok" for r in results)


def test_art_fetch_worker_downloads_image(tmp_path):
    art_dir = tmp_path / "art"
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"FAKEIMAGE"

    songs = [{"id": 42, "art_url": "http://example.com/cover.jpg"}]
    collected = []

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.requests.get", return_value=mock_resp):
        worker = ArtFetchWorker(songs)
        worker.art_ready.connect(lambda sid: collected.append(sid))
        worker.run()  # Call run() directly (not start()) for synchronous testing

    assert (art_dir / "42.jpg").exists()
    assert (art_dir / "42.jpg").read_bytes() == b"FAKEIMAGE"
    assert collected == [42]


def test_art_fetch_worker_skips_existing_cached_file(tmp_path):
    art_dir = tmp_path / "art"
    art_dir.mkdir()
    (art_dir / "7.jpg").write_bytes(b"EXISTING")

    songs = [{"id": 7, "art_url": "http://example.com/cover.jpg"}]

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.requests.get") as mock_get:
        worker = ArtFetchWorker(songs)
        worker.run()
        mock_get.assert_not_called()


def test_art_fetch_worker_skips_on_download_error(tmp_path):
    art_dir = tmp_path / "art"
    songs = [{"id": 99, "art_url": "http://example.com/cover.jpg"}]

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.requests.get", side_effect=Exception("network error")):
        worker = ArtFetchWorker(songs)
        worker.run()  # Must not raise

    assert not (art_dir / "99.jpg").exists()


def test_art_resolve_worker_emits_finished(qtbot):
    conn = MagicMock()
    worker = ArtResolveWorker(conn)
    with patch("gui.workers.bulk_resolve"):
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()


def test_art_resolve_worker_emits_error_on_exception(qtbot):
    conn = MagicMock()
    worker = ArtResolveWorker(conn)
    with patch("gui.workers.bulk_resolve", side_effect=RuntimeError("resolve error")):
        with qtbot.waitSignal(worker.error, timeout=3000) as blocker:
            worker.start()
    assert "resolve error" in blocker.args[0]


def test_art_resolve_worker_calls_bulk_resolve_with_progress_cb(qtbot):
    conn = MagicMock()
    worker = ArtResolveWorker(conn)
    with patch("gui.workers.bulk_resolve") as mock_resolve:
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()
    _, kwargs = mock_resolve.call_args
    assert callable(kwargs.get("progress_cb"))


def test_single_art_worker_resolves_and_downloads(tmp_path):
    art_dir = tmp_path / "art"
    conn = MagicMock()
    song = {"id": 42, "artist": "Daft Punk", "title": "Get Lucky", "art_url": None}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"FAKEIMAGE"
    collected = []

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.musicbrainz_lookup", return_value="http://mb.com/art.jpg"), \
         patch("gui.workers.requests.get", return_value=mock_resp), \
         patch("gui.workers.update_art_url") as mock_update:
        worker = SingleArtWorker(song, conn)
        worker.finished.connect(lambda sid: collected.append(sid))
        worker.run()

    assert (art_dir / "42.jpg").exists()
    assert (art_dir / "42.jpg").read_bytes() == b"FAKEIMAGE"
    assert collected == [42]
    mock_update.assert_called_once_with(conn, 42, "http://mb.com/art.jpg")


def test_single_art_worker_skips_resolve_when_art_url_exists(tmp_path):
    art_dir = tmp_path / "art"
    conn = MagicMock()
    song = {"id": 7, "artist": "Daft Punk", "title": "Get Lucky",
            "art_url": "http://existing.com/art.jpg"}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"FAKEIMAGE"

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.musicbrainz_lookup") as mock_mb, \
         patch("gui.workers.requests.get", return_value=mock_resp):
        worker = SingleArtWorker(song, conn)
        worker.run()

    mock_mb.assert_not_called()
    assert (art_dir / "7.jpg").exists()


def test_single_art_worker_emits_error_on_failure(tmp_path):
    art_dir = tmp_path / "art"
    conn = MagicMock()
    song = {"id": 99, "artist": "Daft Punk", "title": "Get Lucky", "art_url": None}
    errors = []

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.musicbrainz_lookup", side_effect=Exception("network error")):
        worker = SingleArtWorker(song, conn)
        worker.error.connect(lambda e: errors.append(e))
        worker.run()

    assert errors and "network error" in errors[0]


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


def test_parallel_art_worker_resolves_via_itunes_and_downloads(qtbot, tmp_path):
    import sqlite3
    from gui.workers import ParallelArtWorker

    art_dir = tmp_path / "art"
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE album_art (
            id INTEGER PRIMARY KEY, artist TEXT NOT NULL, album TEXT NOT NULL,
            art_url TEXT, UNIQUE(artist, album)
        );
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            album_art_id INTEGER, source TEXT
        );
        INSERT INTO songs VALUES (1, 'Daft Punk', 'Get Lucky', NULL, 'fucuco');
    """)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"IMAGEDATA"
    received = []
    progress_vals = []

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.itunes_lookup", return_value=("RAM", "http://itunes.com/art.jpg")), \
         patch("gui.workers.requests.get", return_value=mock_resp), \
         patch("gui.workers.get_or_create_album_art", wraps=lambda c, ar, al, u: 1) as mock_create, \
         patch("gui.workers.link_song_album_art") as mock_link:
        worker = ParallelArtWorker(conn, n_resolve=1, n_download=1)
        worker.art_ready.connect(lambda sid: received.append(sid))
        worker.progress.connect(lambda v: progress_vals.append(v))
        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.start()

    assert 1 in received
    mock_link.assert_called()
    assert any(v > 0 for v in progress_vals)


def test_parallel_art_worker_falls_back_to_gdrive(qtbot, tmp_path):
    import sqlite3
    from gui.workers import ParallelArtWorker

    art_dir = tmp_path / "art"
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE album_art (
            id INTEGER PRIMARY KEY, artist TEXT NOT NULL, album TEXT NOT NULL,
            art_url TEXT, UNIQUE(artist, album)
        );
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            album_art_id INTEGER, source TEXT
        );
        INSERT INTO songs VALUES (1, 'Daft Punk', 'Get Lucky', NULL, 'fucuco');
    """)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"IMAGEDATA"
    received = []

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.itunes_lookup", return_value=None), \
         patch("gui.workers.gdrive_art_lookup", return_value="http://gdrive.com/art.jpg"), \
         patch("gui.workers.requests.get", return_value=mock_resp), \
         patch("gui.workers.get_or_create_album_art", return_value=1), \
         patch("gui.workers.link_song_album_art"):
        worker = ParallelArtWorker(conn, n_resolve=1, n_download=1)
        worker.art_ready.connect(lambda sid: received.append(sid))
        with qtbot.waitSignal(worker.finished, timeout=5000):
            worker.start()

    assert 1 in received


def test_parallel_art_worker_emits_finished_with_no_pending(qtbot, tmp_path):
    import sqlite3
    from gui.workers import ParallelArtWorker

    art_dir = tmp_path / "art"
    art_dir.mkdir()
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE album_art (
            id INTEGER PRIMARY KEY, artist TEXT NOT NULL, album TEXT NOT NULL,
            art_url TEXT, UNIQUE(artist, album)
        );
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            album_art_id INTEGER, source TEXT
        );
        INSERT INTO album_art VALUES (5, 'Daft Punk', 'RAM', 'http://itunes.com/art.jpg');
        INSERT INTO songs VALUES (1, 'Daft Punk', 'Get Lucky', 5, 'fucuco');
    """)
    (art_dir / "5.jpg").write_bytes(b"CACHED")

    with patch("gui.workers.ART_DIR", art_dir):
        worker = ParallelArtWorker(conn, n_resolve=1, n_download=1)
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()


def test_parallel_art_worker_stop_terminates_gracefully(qtbot, tmp_path):
    import sqlite3
    from gui.workers import ParallelArtWorker

    art_dir = tmp_path / "art"
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE album_art (
            id INTEGER PRIMARY KEY, artist TEXT NOT NULL, album TEXT NOT NULL,
            art_url TEXT, UNIQUE(artist, album)
        );
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            album_art_id INTEGER, source TEXT
        );
        INSERT INTO songs VALUES (1, 'Artist A', 'Song X', NULL, 'fucuco');
    """)

    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.itunes_lookup", return_value=None), \
         patch("gui.workers.gdrive_art_lookup", return_value=None):
        worker = ParallelArtWorker(conn, n_resolve=1, n_download=1)
        worker.start()
        worker.stop()
        with qtbot.waitSignal(worker.finished, timeout=5000):
            pass

    assert worker._cancel.is_set()


def test_parallel_art_worker_skips_existing_file(qtbot, tmp_path):
    """Song with existing album_art_id and existing file should emit art_ready without downloading."""
    import sqlite3
    from gui.workers import ParallelArtWorker

    art_dir = tmp_path / "art"
    art_dir.mkdir()
    (art_dir / "3.jpg").write_bytes(b"CACHED")

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE album_art (
            id INTEGER PRIMARY KEY, artist TEXT NOT NULL, album TEXT NOT NULL,
            art_url TEXT, UNIQUE(artist, album)
        );
        CREATE TABLE songs (
            id INTEGER PRIMARY KEY, artist TEXT, title TEXT,
            album_art_id INTEGER, source TEXT
        );
        INSERT INTO album_art VALUES (3, 'Artist C', 'Album C', 'http://ex.com/3.jpg');
        INSERT INTO songs VALUES (2, 'Artist C', 'Song Z', 3, 'fucuco');
    """)

    received = []
    with patch("gui.workers.ART_DIR", art_dir), \
         patch("gui.workers.requests.get") as mock_get:
        worker = ParallelArtWorker(conn, n_resolve=1, n_download=1)
        worker.art_ready.connect(lambda sid: received.append(sid))
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()
        mock_get.assert_not_called()

    assert 2 in received
