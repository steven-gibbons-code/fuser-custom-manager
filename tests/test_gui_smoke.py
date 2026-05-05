def test_gui_imports():
    from gui.main_window import FuserApp
    from gui.song_table import SongTable
    from gui.detail_panel import DetailPanel
    from gui.status_bar import StatusBar
    assert FuserApp and SongTable and DetailPanel and StatusBar
