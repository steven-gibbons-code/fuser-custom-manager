from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QSize, Signal
from PySide6.QtWidgets import QTableView, QAbstractItemView


class SongTableModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []

    def reset(self, rows: list[dict]):
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def get_row(self, index: int) -> dict:
        return self._rows[index]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        if role == Qt.ItemDataRole.UserRole:
            return self._rows[index.row()]
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        return None


class SongTableView(QTableView):
    visibleSongsChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.horizontalHeader().hide()
        self.setWordWrap(False)
        self.setMouseTracking(True)

    def set_model(self, model: SongTableModel):
        from gui.song_delegate import SongRowDelegate, ROW_HEIGHT
        self.setModel(model)
        self.setItemDelegate(SongRowDelegate(self))
        self.verticalHeader().setDefaultSectionSize(ROW_HEIGHT + 6)
        self.horizontalHeader().setStretchLastSection(True)
        model.modelReset.connect(self._emit_visible_songs)
        self.verticalScrollBar().valueChanged.connect(self._emit_visible_songs)
        self._emit_visible_songs()

    def _emit_visible_songs(self) -> None:
        if self.model() is None:
            return
        vp = self.viewport()
        first = self.rowAt(0)
        if first < 0:
            return
        last = self.rowAt(vp.height() - 1)
        if last < 0:
            last = self.model().rowCount() - 1
        song_ids = []
        for row in range(first, last + 1):
            idx = self.model().index(row, 0)
            song = idx.data(Qt.ItemDataRole.UserRole)
            if song and "id" in song:
                song_ids.append(song["id"])
        if song_ids:
            self.visibleSongsChanged.emit(song_ids)

    def get_selected_songs(self) -> list[dict]:
        if self.model() is None:
            return []
        return [
            idx.data(Qt.ItemDataRole.UserRole)
            for idx in self.selectionModel().selectedRows()
        ]

    def select_all(self):
        self.selectAll()

    def deselect_all(self):
        self.clearSelection()

    def set_batch_mode(self, enabled: bool):
        if enabled:
            self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        else:
            self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
