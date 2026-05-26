import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gui.detail_panel import DetailPanel

SONG = {
    "id": 1, "title": "Get Lucky", "artist": "Daft Punk", "bpm": 116,
    "key": "A Minor", "genre": "Pop", "year": 2013,
    "submit_date": "2024/03/01", "source": "fucuco_main",
    "de_status": "Eligible", "complete": "C", "complete_notes": "",
    "origin": None, "stream_opt": 1,
    "link": "https://drive.google.com/file/d/abc",
    "pak_path": None, "quality": "Complete",
}

INSTALLED_SONG = {**SONG, "pak_path": "/path/to/get_lucky.pak"}


def test_initial_state_no_song(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    assert panel._song is None


def test_show_populates_title(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    assert panel._song == SONG
    assert panel._labels["title"].text() == "Get Lucky"


def test_show_populates_artist(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    assert panel._labels["artist"].text() == "Daft Punk"


def test_download_btn_enabled_when_not_installed(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    assert panel._dl_btn.isEnabled()


def test_download_btn_disabled_when_installed(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(INSTALLED_SONG)
    assert not panel._dl_btn.isEnabled()


def test_uninstall_btn_enabled_when_installed(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(INSTALLED_SONG)
    assert panel._un_btn.isEnabled()


def test_uninstall_btn_disabled_when_not_installed(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    assert not panel._un_btn.isEnabled()


def test_download_requested_signal(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    with qtbot.waitSignal(panel.download_requested, timeout=1000) as blocker:
        panel._dl_btn.click()
    assert blocker.args[0]["title"] == "Get Lucky"


def test_uninstall_requested_signal(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(INSTALLED_SONG)
    with qtbot.waitSignal(panel.uninstall_requested, timeout=1000) as blocker:
        panel._un_btn.click()
    assert blocker.args[0]["id"] == 1


def test_stream_opt_displays_yes_no(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    assert panel._labels["stream_opt"].text() == "Yes"
    panel.show({**SONG, "stream_opt": 0})
    assert panel._labels["stream_opt"].text() == "No"


def test_complete_field_mapped(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show({**SONG, "complete": "D"})
    assert panel._labels["complete"].text() == "Definitive"
