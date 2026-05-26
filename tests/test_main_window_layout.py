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
