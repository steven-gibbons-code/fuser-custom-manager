import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.status_bar import StatusBar


def test_initial_state(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.show()
    assert bar._lbl.text() == "Ready"
    assert not bar._progress.isVisible()


def test_set_message(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.show()
    bar.set_message("Scanning…")
    assert bar._lbl.text() == "Scanning…"
    assert not bar._progress.isVisible()


def test_start_download_shows_progress(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.show()
    bar.start_download("Get Lucky")
    assert "Get Lucky" in bar._lbl.text()
    assert bar._progress.isVisible()
    assert bar._progress.value() == 0


def test_set_progress_updates_bar(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.show()
    bar.start_download("Get Lucky")
    bar.set_progress(0.5)
    assert bar._progress.value() == 50


def test_set_done_hides_progress_after_delay(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.show()
    bar.set_done("Get Lucky")
    assert "Get Lucky" in bar._lbl.text()
    assert bar._progress.value() == 100


def test_set_error(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.show()
    bar.set_error("Download failed")
    assert "Download failed" in bar._lbl.text()
    assert not bar._progress.isVisible()


def test_set_error_label_color(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.show()
    bar.set_error("failed")
    assert "#ef5350" in bar._lbl.styleSheet()  # danger token


def test_set_idle(qtbot):
    bar = StatusBar()
    qtbot.addWidget(bar)
    bar.show()
    bar.start_download("test")
    bar.set_idle()
    assert bar._lbl.text() == "Ready"
    assert not bar._progress.isVisible()
