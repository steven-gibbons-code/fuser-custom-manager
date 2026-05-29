import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock
from gui.main_window import FuserApp


def _make_app(qtbot):
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (0,)
    with patch("gui.main_window.init_db", return_value=mock_conn), \
         patch("gui.main_window.scan_and_sync"), \
         patch("gui.main_window.get_setting", return_value=None), \
         patch("gui.main_window.get_songs", return_value=[]):
        window = FuserApp()
    qtbot.addWidget(window)
    return window


def test_splitter_has_stretch_factor_1(qtbot):
    window = _make_app(qtbot)
    layout = window.centralWidget().layout()
    # Layout order: 0=filter_bar, 1=batch_bar, 2=splitter, 3=status_bar
    assert layout.stretch(2) == 1


def test_check_dates_stale_query_excludes_fusersoundlab(qtbot):
    """Stale-date count must not include fusersoundlab rows (they never have dates)."""
    window = _make_app(qtbot)
    window.conn.execute.reset_mock()
    window.conn.execute.return_value.fetchone.return_value = (0,)
    window._check_dates_stale()
    sql = window.conn.execute.call_args[0][0]
    assert "fusersoundlab" in sql, "query should exclude fusersoundlab source"


def test_check_dates_stale_clears_status_bar_when_zero(qtbot):
    """When stale count reaches 0, status bar should return to idle (not keep old message)."""
    window = _make_app(qtbot)
    window.status_bar.set_message("99 songs have no date — click Refresh Sources to update.")
    window.conn.execute.return_value.fetchone.return_value = (0,)
    window._check_dates_stale()
    assert window.status_bar._lbl.text() == "Ready"


def test_on_refresh_done_reruns_stale_check(qtbot):
    """_on_refresh_done must call _check_dates_stale so the status bar updates."""
    from unittest.mock import patch
    window = _make_app(qtbot)
    with patch.object(window, "_check_dates_stale") as mock_check, \
         patch.object(window, "_refresh_table"):
        window._on_refresh_done()
    mock_check.assert_called_once()


def test_fetch_art_button_exists_in_toolbar(qtbot):
    window = _make_app(qtbot)
    assert hasattr(window, "_fetch_art_btn")
    assert window._fetch_art_btn.text() == "↓ Fetch Art"


def test_on_refresh_done_re_enables_buttons_when_no_art(qtbot):
    window = _make_app(qtbot)
    with patch.object(window, "_check_dates_stale"), \
         patch.object(window, "_refresh_table"), \
         patch.object(window, "_set_action_buttons_enabled") as mock_enable:
        window._on_refresh_done(include_art=False)
    mock_enable.assert_called_once_with(True)


def test_on_refresh_done_calls_art_resolve_when_include_art(qtbot):
    window = _make_app(qtbot)
    with patch.object(window, "_check_dates_stale"), \
         patch.object(window, "_refresh_table"), \
         patch.object(window, "_start_art_resolve") as mock_resolve:
        window._on_refresh_done(include_art=True)
    mock_resolve.assert_called_once()


def test_fetch_art_for_song_starts_single_art_worker(qtbot):
    window = _make_app(qtbot)
    song = {"id": 42, "artist": "Daft Punk", "title": "Get Lucky",
            "art_url": None, "pak_path": None}
    with patch("gui.main_window.SingleArtWorker") as MockWorker:
        mock_instance = MagicMock()
        MockWorker.return_value = mock_instance
        window._fetch_art_for_song(song)
    MockWorker.assert_called_once_with(song, window.conn)
    mock_instance.start.assert_called_once()


def test_start_art_resolve_guard_prevents_double_start(qtbot):
    """_start_art_resolve must not create a second worker if one is already running."""
    window = _make_app(qtbot)
    with patch("gui.main_window.ParallelArtWorker") as MockWorker, \
         patch("gui.main_window.count_pending_art", return_value=0):
        mock_instance = MagicMock()
        mock_instance.isRunning.return_value = True
        MockWorker.return_value = mock_instance

        window._start_art_resolve()   # first call — starts the worker
        window._art_worker = mock_instance  # simulate running state
        window._start_art_resolve()   # second call — should be a no-op

    assert MockWorker.call_count == 1


def test_on_art_resolve_done_clears_art_worker_and_resets_button(qtbot):
    """_on_art_resolve_done must null the worker and restore the fetch-art button label."""
    window = _make_app(qtbot)
    # Simulate a finished state: button is in "stop" mode, worker is set
    mock_worker = MagicMock()
    mock_worker.prioritize = MagicMock()
    window._art_worker = mock_worker
    window._fetch_art_btn.setText("✕ Stop Fetch")

    window._on_art_resolve_done()

    assert window._art_worker is None
    assert window._fetch_art_btn.text() == "↓ Fetch Art"
