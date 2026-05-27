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
