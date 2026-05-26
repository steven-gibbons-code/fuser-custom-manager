import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtCore import Qt
from gui.song_table import SongTableModel, COL_TITLE, COL_ARTIST, COL_BPM, COL_QUALITY, COL_SOURCE, COL_INSTALLED

SONGS = [
    {"id": 1, "title": "Get Lucky", "artist": "Daft Punk", "bpm": 116,
     "quality": "Complete", "source": "fucuco_main", "pak_path": "/some/path.pak"},
    {"id": 2, "title": "Come As You Are", "artist": "Nirvana", "bpm": 120,
     "quality": "Definitive", "source": "fusersoundlab", "pak_path": None},
]


def test_initial_row_count_is_zero(qtbot):
    model = SongTableModel()
    assert model.rowCount() == 0


def test_reset_updates_row_count(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    assert model.rowCount() == 2


def test_column_count(qtbot):
    model = SongTableModel()
    assert model.columnCount() == 6


def test_data_title(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(0, COL_TITLE)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "Get Lucky"


def test_data_artist(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(0, COL_ARTIST)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "Daft Punk"


def test_data_bpm(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(0, COL_BPM)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "116"


def test_data_quality(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(0, COL_QUALITY)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "Complete"


def test_data_source(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(0, COL_SOURCE)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) == "fucuco_main"


def test_data_installed_returns_none_for_display(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(0, COL_INSTALLED)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) is None


def test_user_role_returns_song_dict(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(1, COL_TITLE)
    song = model.data(idx, Qt.ItemDataRole.UserRole)
    assert song["artist"] == "Nirvana"


def test_get_row(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    assert model.get_row(0)["title"] == "Get Lucky"
    assert model.get_row(1)["artist"] == "Nirvana"


def test_header_data(qtbot):
    model = SongTableModel()
    assert model.headerData(COL_TITLE, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "Title"
    assert model.headerData(COL_ARTIST, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "Artist"


def test_reset_replaces_rows(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    model.reset([SONGS[0]])
    assert model.rowCount() == 1
    assert model.get_row(0)["title"] == "Get Lucky"


from gui.song_table import _QUALITY_COLORS


def test_quality_color_complete():
    bg, fg = _QUALITY_COLORS["Complete"]
    assert bg == "#2e2000"
    assert fg == "#d4a017"


def test_quality_color_definitive():
    bg, fg = _QUALITY_COLORS["Definitive"]
    assert bg == "#252530"
    assert fg == "#a0a8b8"


def test_quality_color_official():
    bg, fg = _QUALITY_COLORS["Official"]
    assert bg == "#1a1535"
    assert fg == "#8b7de8"


def test_quality_color_other_unchanged():
    bg, fg = _QUALITY_COLORS["Other"]
    assert bg == "#2a2a2a"
    assert fg == "#888888"


def test_background_role_installed_row_is_dark_green(qtbot):
    model = SongTableModel()
    model.reset([{
        "id": 1, "title": "T", "artist": "A", "bpm": 120,
        "quality": "Complete", "source": "s", "pak_path": "/foo.pak",
    }])
    idx = model.index(0, COL_TITLE)
    brush = model.data(idx, Qt.ItemDataRole.BackgroundRole)
    assert brush is not None
    assert brush.color().name() == "#152215"


def test_background_role_uninstalled_row_is_none(qtbot):
    model = SongTableModel()
    model.reset([{
        "id": 2, "title": "T", "artist": "A", "bpm": 120,
        "quality": "Complete", "source": "s", "pak_path": None,
    }])
    idx = model.index(0, COL_TITLE)
    brush = model.data(idx, Qt.ItemDataRole.BackgroundRole)
    assert brush is None


def test_background_role_not_set_for_installed_column(qtbot):
    model = SongTableModel()
    model.reset([{
        "id": 1, "title": "T", "artist": "A", "bpm": 120,
        "quality": "Complete", "source": "s", "pak_path": "/foo.pak",
    }])
    idx = model.index(0, COL_INSTALLED)
    brush = model.data(idx, Qt.ItemDataRole.BackgroundRole)
    assert brush is None
