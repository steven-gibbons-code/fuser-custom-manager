import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtCore import Qt
from gui.song_table import SongTableModel

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
    assert model.columnCount() == 1


def test_display_role_returns_none(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(0, 0)
    assert model.data(idx, Qt.ItemDataRole.DisplayRole) is None


def test_user_role_returns_song_dict(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    idx = model.index(1, 0)
    song = model.data(idx, Qt.ItemDataRole.UserRole)
    assert song["artist"] == "Nirvana"


def test_get_row(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    assert model.get_row(0)["title"] == "Get Lucky"
    assert model.get_row(1)["artist"] == "Nirvana"


def test_reset_replaces_rows(qtbot):
    model = SongTableModel()
    model.reset(SONGS)
    model.reset([SONGS[0]])
    assert model.rowCount() == 1
    assert model.get_row(0)["title"] == "Get Lucky"


def test_song_table_view_emits_visible_songs_on_scroll(qtbot):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from PySide6.QtWidgets import QApplication
    from gui.song_table import SongTableModel, SongTableView

    _app = QApplication.instance() or QApplication([])

    model = SongTableModel()
    model.reset([
        {"id": 1, "artist": "A", "title": "X"},
        {"id": 2, "artist": "B", "title": "Y"},
    ])

    view = SongTableView()
    view.resize(400, 600)

    emitted = []
    view.visibleSongsChanged.connect(lambda ids: emitted.extend(ids))

    view.set_model(model)
    view.show()
    qtbot.addWidget(view)

    assert len(emitted) > 0
    assert all(isinstance(sid, int) for sid in emitted)
