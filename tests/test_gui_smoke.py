def test_gui_imports():
    from gui.main_window import FuserApp
    from gui.song_table import SongTableModel, SongTableView
    from gui.detail_panel import DetailPanel
    from gui.status_bar import StatusBar
    from gui.filter_bar import FilterBar
    from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker
    from gui.settings_dialog import SettingsDialog
    from gui.batch_results_dialog import BatchResultsDialog
    assert all([FuserApp, SongTableModel, SongTableView, DetailPanel, StatusBar,
                FilterBar, RefreshWorker, DownloadWorker, BatchDownloadWorker,
                SettingsDialog, BatchResultsDialog])
