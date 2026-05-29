import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch
from PySide6.QtCore import Qt
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


# ── Pills row ──────────────────────────────────────────────────────────────

def test_quality_pill_shows_tier_text(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    assert panel._quality_pill.text() == "Complete"


def test_quality_pill_uses_tier_color(qtbot):
    from gui.tokens import TOKENS
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    style = panel._quality_pill.styleSheet()
    assert TOKENS["tier_complete_bg"] in style


def test_quality_pill_not_green_when_installed(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(INSTALLED_SONG)
    # installed state shows card tint in the delegate, not a green pill
    assert "✓" not in panel._quality_pill.text()
    assert panel._quality_pill.text() == "Complete"


def test_key_pill_shows_value(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    assert panel._key_pill.text() == "A Minor"


def test_key_pill_shows_dash_when_empty(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show({**SONG, "key": None})
    assert panel._key_pill.text() == "—"


def test_bpm_pill_shows_value(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    assert panel._bpm_pill.text() == "116 BPM"


def test_bpm_pill_shows_dash_when_missing(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show({**SONG, "bpm": None})
    assert panel._bpm_pill.text() == "—"


def test_clear_resets_all_pills(qtbot):
    panel = DetailPanel()
    qtbot.addWidget(panel)
    panel.show(SONG)
    panel.clear()
    assert panel._quality_pill.text() == "—"
    assert panel._key_pill.text() == "—"
    assert panel._bpm_pill.text() == "—"


# ── Art overlay button ─────────────────────────────────────────────────────

_SONG_NO_ART = {"id": 42, "album_art_id": None, "pak_path": None}
_SONG_WITH_ART = {"id": 42, "album_art_id": 7, "pak_path": None}


def test_overlay_visible_when_no_art_on_disk(qtbot, tmp_path):
    art_dir = tmp_path / "art"  # directory doesn't exist — no cached file
    with patch("gui.detail_panel.ART_DIR", art_dir):
        panel = DetailPanel()
        qtbot.addWidget(panel)
        panel.show(_SONG_NO_ART)
        assert not panel._art_overlay_btn.isHidden()


def test_overlay_hidden_when_art_on_disk(qtbot, tmp_path):
    art_dir = tmp_path / "art"
    art_dir.mkdir()
    (art_dir / "7.jpg").write_bytes(b"FAKE")  # keyed by album_art_id
    with patch("gui.detail_panel.ART_DIR", art_dir):
        panel = DetailPanel()
        qtbot.addWidget(panel)
        panel.show(_SONG_WITH_ART)
        assert panel._art_overlay_btn.isHidden()


def test_overlay_visible_when_album_art_id_present_but_file_missing(qtbot, tmp_path):
    art_dir = tmp_path / "art"
    art_dir.mkdir()
    # album_art_id is set but file not downloaded yet
    with patch("gui.detail_panel.ART_DIR", art_dir):
        panel = DetailPanel()
        qtbot.addWidget(panel)
        panel.show(_SONG_WITH_ART)
        assert not panel._art_overlay_btn.isHidden()


def test_overlay_hidden_on_clear(qtbot, tmp_path):
    art_dir = tmp_path / "art"
    with patch("gui.detail_panel.ART_DIR", art_dir):
        panel = DetailPanel()
        qtbot.addWidget(panel)
        panel.show(_SONG_NO_ART)
        panel.clear()
        assert panel._art_overlay_btn.isHidden()


def test_fetch_art_requested_emitted_on_click(qtbot, tmp_path):
    art_dir = tmp_path / "art"
    emitted = []
    with patch("gui.detail_panel.ART_DIR", art_dir):
        panel = DetailPanel()
        qtbot.addWidget(panel)
        panel.fetch_art_requested.connect(lambda s: emitted.append(s))
        panel.show(_SONG_NO_ART)
        qtbot.mouseClick(panel._art_overlay_btn, Qt.MouseButton.LeftButton)
    assert len(emitted) == 1
    assert emitted[0]["id"] == 42
