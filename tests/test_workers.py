import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock
from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker


def test_refresh_worker_emits_finished(qtbot, tmp_path):
    conn = MagicMock()
    worker = RefreshWorker(conn)
    mock_songs = [{"title": "A"}, {"title": "B"}]
    with patch("gui.workers.fetch_fucuco", return_value=[mock_songs[0]]), \
         patch("gui.workers.fetch_fsl", return_value=[mock_songs[1]]), \
         patch("gui.workers.upsert_songs") as mock_upsert:
        with qtbot.waitSignal(worker.finished, timeout=3000):
            worker.start()
        mock_upsert.assert_called_once()


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
