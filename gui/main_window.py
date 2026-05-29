import sqlite3
from datetime import date
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QFrame, QLabel, QDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmapCache

from db import init_db, get_songs, get_song_by_id, get_setting, set_setting, count_pending_art
from installer import scan_and_sync, uninstall, install_manual_files, DEFAULT_INSTALL_DIR

from gui.filter_bar import FilterBar
from gui.song_table import SongTableModel, SongTableView
from gui.detail_panel import DetailPanel
from gui.status_bar import StatusBar
from gui.workers import RefreshWorker, DownloadWorker, BatchDownloadWorker, ParallelArtWorker, SingleArtWorker
from gui.settings_dialog import SettingsDialog
from gui.batch_results_dialog import BatchResultsDialog
from gui.refresh_mode_dialog import RefreshModeDialog
from gui.widgets.stage_backdrop import StageBackdrop
from gui.widgets.fuser_label import FuserLabel


class FuserApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fuser Custom Song Manager")
        self.resize(1200, 800)
        self.setMinimumSize(800, 600)

        _icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"
        if _icon_path.exists():
            self.setWindowIcon(QIcon(str(_icon_path)))

        self.conn: sqlite3.Connection = init_db()
        path_str = get_setting(self.conn, "install_path")
        self._install_dir = Path(path_str) if path_str else DEFAULT_INSTALL_DIR
        self._batch_mode = False
        self._active_worker = None
        self._art_worker = None
        self._single_art_worker = None

        scan_and_sync(self._install_dir, self.conn)
        self._build_ui()
        self._refresh_table()
        self._check_dates_stale()

    # ── Layout ────────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._backdrop = StageBackdrop(central)

        self.filter_bar = FilterBar()
        self.filter_bar.filters_changed.connect(self._on_filters_changed)
        self.filter_bar._refresh_btn.clicked.connect(self._start_refresh)
        self.filter_bar._settings_btn.clicked.connect(self._open_settings)
        self._batch_btn = QPushButton("☰ Batch Mode")
        self._batch_btn.clicked.connect(self._enter_batch_mode)

        self._fetch_art_btn = QPushButton("↓ Fetch Art")
        self._fetch_art_btn.clicked.connect(self._start_art_resolve)
        self.filter_bar.add_to_toolbar(self._fetch_art_btn)
        self.filter_bar.add_to_toolbar(self._batch_btn)
        self.filter_bar.add_to_toolbar(self.filter_bar._settings_btn)
        root.addWidget(self.filter_bar)

        self._fuser_lbl = FuserLabel("FUSER", pt_size=22)
        self.filter_bar.prepend_to_toolbar(self._fuser_lbl)

        self._model = SongTableModel()
        self.song_table = SongTableView()
        self.song_table.set_model(self._model)

        self._batch_bar = self._build_batch_bar()
        self._batch_bar.hide()
        root.addWidget(self._batch_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.song_table.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        splitter.addWidget(self.song_table)

        self.detail_panel = DetailPanel()
        self.detail_panel.setObjectName("detailPanel")
        self.detail_panel.download_requested.connect(self._on_download)
        self.detail_panel.uninstall_requested.connect(self._on_uninstall)
        self.detail_panel.manual_install_requested.connect(self._on_manual_install)
        self.detail_panel.fetch_art_requested.connect(self._fetch_art_for_song)
        splitter.addWidget(self.detail_panel)

        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        root.addWidget(splitter, stretch=1)

        self.status_bar = StatusBar()
        root.addWidget(self.status_bar)

        self._backdrop.lower()
        self._backdrop.resize(central.size())

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "_backdrop"):
            self._backdrop.resize(self.centralWidget().size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_backdrop"):
            self._backdrop.resize(self.centralWidget().size())

    def closeEvent(self, event):
        for worker in (self._art_worker, self._single_art_worker, self._active_worker):
            if worker is not None and worker.isRunning():
                if hasattr(worker, "stop"):
                    worker.stop()
                worker.wait(3000)
        event.accept()

    def _build_batch_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("batchbar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.clicked.connect(self.song_table.select_all)
        layout.addWidget(self._select_all_btn)

        self._deselect_all_btn = QPushButton("Deselect All")
        self._deselect_all_btn.clicked.connect(self.song_table.deselect_all)
        layout.addWidget(self._deselect_all_btn)

        layout.addStretch()

        self._download_btn = QPushButton("Download (0)")
        self._download_btn.setObjectName("downloadBtn")
        self._download_btn.setEnabled(False)
        self._download_btn.clicked.connect(self._on_batch_download)
        layout.addWidget(self._download_btn)

        self._exit_batch_btn = QPushButton("✕ Exit Batch")
        self._exit_batch_btn.clicked.connect(self._exit_batch_mode)
        layout.addWidget(self._exit_batch_btn)

        return bar

    # ── Data ──────────────────────────────────────────────────────────────

    def _refresh_table(self):
        filters = self.filter_bar.get_filters()
        rows = get_songs(self.conn, filters, limit=0)
        self._model.reset(rows)

    def _on_filters_changed(self, _filters: dict):
        self._refresh_table()

    def _check_dates_stale(self):
        null_dates = self.conn.execute(
            "SELECT COUNT(*) FROM songs WHERE submit_date IS NULL"
            " AND source != 'fusersoundlab'"
        ).fetchone()[0]
        if null_dates > 0:
            self.status_bar.set_message(
                f"{null_dates:,} songs have no date — click Refresh Sources to update."
            )
        else:
            self.status_bar.set_idle()

    def _set_action_buttons_enabled(self, enabled: bool):
        self.filter_bar.set_refresh_enabled(enabled)
        self._fetch_art_btn.setEnabled(enabled)

    # ── Selection ─────────────────────────────────────────────────────────

    def _on_selection_changed(self):
        if self._batch_mode:
            count = len(self.song_table.get_selected_songs())
            self._download_btn.setText(f"Download ({count})")
            self._download_btn.setEnabled(count > 0)
            return
        indexes = self.song_table.selectionModel().selectedRows()
        if not indexes:
            return
        song = self._model.get_row(indexes[0].row())
        self.detail_panel.show(song)

    # ── Batch mode ────────────────────────────────────────────────────────

    def _enter_batch_mode(self):
        self._batch_mode = True
        self._batch_btn.hide()
        self.detail_panel.hide()
        self._batch_bar.show()
        self.song_table.set_batch_mode(True)

    def _exit_batch_mode(self):
        self._batch_mode = False
        self.song_table.deselect_all()
        self.song_table.set_batch_mode(False)
        self._batch_bar.hide()
        self._batch_btn.show()
        self.detail_panel.setVisible(True)
        self._download_btn.setText("Download (0)")
        self._download_btn.setEnabled(False)

    def _on_batch_download(self):
        songs = self.song_table.get_selected_songs()
        to_download = [s for s in songs if not s.get("pak_path")]
        already_installed = [s for s in songs if s.get("pak_path")]
        if not to_download:
            skipped = [
                {"song": s, "status": "skipped", "message": "Already installed"}
                for s in already_installed
            ]
            self._show_batch_results(skipped)
            return
        self._download_btn.setEnabled(False)
        self._download_btn.setText("Downloading…")
        worker = BatchDownloadWorker(to_download, self._install_dir, self.conn)
        skipped = [
            {"song": s, "status": "skipped", "message": "Already installed"}
            for s in already_installed
        ]
        worker.item_progress.connect(self.status_bar.set_message)
        worker.finished.connect(lambda results: self._on_batch_done(results + skipped))
        self._active_worker = worker
        worker.start()

    def _on_batch_done(self, results: list[dict]):
        self._refresh_table()
        self.status_bar.set_idle()
        self._show_batch_results(results)

    def _show_batch_results(self, results: list[dict]):
        dlg = BatchResultsDialog(results, parent=self)
        dlg.closed.connect(self._exit_batch_mode)
        dlg.exec()

    # ── Refresh sources ───────────────────────────────────────────────────

    def _start_refresh(self):
        pending = count_pending_art(self.conn)
        include_art = False
        if pending > 0:
            dlg = RefreshModeDialog(pending, parent=self)
            include_art = dlg.exec() == QDialog.DialogCode.Accepted

        self._set_action_buttons_enabled(False)
        worker = RefreshWorker(self.conn)
        worker.status.connect(self.status_bar.set_message)
        worker.error.connect(self.status_bar.set_error)
        worker.error.connect(lambda _: self._set_action_buttons_enabled(True))
        worker.finished.connect(lambda: self._on_refresh_done(include_art))
        self._active_worker = worker
        worker.start()

    def _on_refresh_done(self, include_art: bool = False):
        self.filter_bar.set_updated_label(f"Updated {date.today().isoformat()}")
        self._refresh_table()
        self._check_dates_stale()
        if include_art:
            self._start_art_resolve()
        else:
            self._set_action_buttons_enabled(True)

    def _start_art_resolve(self):
        self._set_action_buttons_enabled(False)
        self._fetch_art_btn.setEnabled(True)  # re-enable as stop button
        self._fetch_art_btn.setText("✕ Stop Fetch")
        self._fetch_art_btn.clicked.disconnect(self._start_art_resolve)
        self._fetch_art_btn.clicked.connect(self._cancel_art_resolve)

        pending = count_pending_art(self.conn)
        self.status_bar.start_art_resolve(pending)
        worker = ParallelArtWorker(self.conn)
        worker.status.connect(self.status_bar.set_message)
        worker.progress.connect(self.status_bar.set_progress)
        worker.art_ready.connect(self._on_art_ready)
        worker.finished.connect(self._on_art_resolve_done)
        self.song_table.visibleSongsChanged.connect(worker.prioritize)
        worker.finished.connect(
            lambda: self.song_table.visibleSongsChanged.disconnect(worker.prioritize)
        )
        self._art_worker = worker
        worker.start()
        self.song_table.emit_visible_songs()

    def _cancel_art_resolve(self):
        if self._art_worker:
            self._art_worker.stop()
        self._fetch_art_btn.setEnabled(False)
        self._fetch_art_btn.setText("Stopping…")
        self.status_bar.set_message("Stopping art fetch…")

    def _on_art_resolve_done(self):
        self._art_worker = None
        self._fetch_art_btn.setText("↓ Fetch Art")
        try:
            self._fetch_art_btn.clicked.disconnect(self._cancel_art_resolve)
        except RuntimeError:
            pass
        self._fetch_art_btn.clicked.connect(self._start_art_resolve)
        self._set_action_buttons_enabled(True)
        self.status_bar.set_idle()

    def _on_art_ready(self, song_id: int):
        QPixmapCache.remove(f"art_{song_id}_48")
        QPixmapCache.remove(f"art_{song_id}_240")
        refreshed = get_song_by_id(self.conn, song_id)
        if refreshed:
            self.song_table.model().update_song(song_id, refreshed)
        self.song_table.viewport().update()
        if (self.detail_panel._song
                and self.detail_panel._song.get("id") == song_id):
            self.detail_panel.show(refreshed or self.detail_panel._song)

    def _fetch_art_for_song(self, song: dict):
        worker = SingleArtWorker(song, self.conn)
        worker.status.connect(self.status_bar.set_message)
        worker.error.connect(self.status_bar.set_error)
        worker.finished.connect(self._on_art_ready)
        self._single_art_worker = worker
        worker.start()

    # ── Download / install ────────────────────────────────────────────────

    def _on_download(self, song: dict):
        self.status_bar.start_download(song["title"])
        worker = DownloadWorker(song, self._install_dir, self.conn)
        worker.progress.connect(self.status_bar.set_progress)
        worker.done.connect(self._on_download_done)
        worker.manual.connect(self.detail_panel.show_manual_link)
        worker.manual.connect(lambda _: self.status_bar.set_idle())
        worker.error.connect(self.status_bar.set_error)
        self._active_worker = worker
        worker.start()

    def _on_download_done(self, title: str):
        self._refresh_table()
        self.status_bar.set_done(title)
        indexes = self.song_table.selectionModel().selectedRows()
        if indexes:
            song = self._model.get_row(indexes[0].row())
            fresh = get_song_by_id(self.conn, song["id"])
            if fresh:
                self.detail_panel.show(fresh)

    def _on_uninstall(self, song: dict):
        uninstall(song["id"], self._install_dir, self.conn)
        self._refresh_table()
        fresh = get_song_by_id(self.conn, song["id"])
        if fresh:
            self.detail_panel.show(fresh)

    def _on_manual_install(self, song, pak_path, sig_path):
        install_manual_files(song["id"], song["artist"], pak_path, sig_path,
                             self._install_dir, self.conn)
        self._refresh_table()
        fresh = get_song_by_id(self.conn, song["id"])
        if fresh:
            self.detail_panel.show(fresh)

    # ── Settings ──────────────────────────────────────────────────────────

    def _open_settings(self):
        dlg = SettingsDialog(self._install_dir, self.conn, parent=self)
        dlg.path_saved.connect(self._on_path_saved)
        dlg.exec()

    def _on_path_saved(self, new_path: Path):
        self._install_dir = new_path
        self.status_bar.set_message(f"Install path: {new_path}")
        self._refresh_table()

    def mainloop(self):
        """Compatibility shim so app.py doesn't need changes."""
        from PySide6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        self.show()
        app.exec()
