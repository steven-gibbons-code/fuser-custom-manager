import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock

from gui.main_window import FuserApp
from gui.song_table import SongTableModel, SongTableView
from gui.detail_panel import DetailPanel
from gui.status_bar import StatusBar
from gui.filter_bar import FilterBar
from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker
from gui.settings_dialog import SettingsDialog
from gui.batch_results_dialog import BatchResultsDialog
from gui.widgets.stage_backdrop import StageBackdrop
from gui.widgets.fuser_label import FuserLabel


def _make_app(qtbot):
    """Boot FuserApp with all external calls mocked out."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchone.return_value = (0,)
    with patch("gui.main_window.init_db", return_value=mock_conn), \
         patch("gui.main_window.scan_and_sync"), \
         patch("gui.main_window.get_setting", return_value=None), \
         patch("gui.main_window.get_songs", return_value=[]):
        window = FuserApp()
    qtbot.addWidget(window)
    return window


def test_gui_imports():
    assert all([FuserApp, SongTableModel, SongTableView, DetailPanel, StatusBar,
                FilterBar, RefreshWorker, DownloadWorker, BatchDownloadWorker,
                SettingsDialog, BatchResultsDialog])


def test_stage_backdrop_is_child_of_central_widget(qtbot):
    window = _make_app(qtbot)
    children = window.centralWidget().children()
    assert any(isinstance(c, StageBackdrop) for c in children)


def test_fuser_label_in_topbar(qtbot):
    window = _make_app(qtbot)
    all_widgets = window.findChildren(FuserLabel)
    assert len(all_widgets) >= 1
