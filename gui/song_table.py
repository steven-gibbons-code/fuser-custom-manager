from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QSize
from PySide6.QtWidgets import (
    QTableView, QStyledItemDelegate, QAbstractItemView,
)

# Column constants kept for get_songs() filter compatibility and tests
COL_INSTALLED = 0
COL_QUALITY   = 1
COL_TITLE     = 2
COL_ARTIST    = 3
COL_KEY       = 4
COL_BPM       = 5
COL_SOURCE    = 6
NUM_COLS      = 7


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

    def get_selected_songs(self) -> list[dict]:
        m = self.model()
        if m is None:
            return []
        return [m.get_row(idx.row()) for idx in self.selectionModel().selectedRows()]

    def select_all(self):
        self.selectAll()

    def deselect_all(self):
        self.clearSelection()

    def set_batch_mode(self, enabled: bool):
        if enabled:
            self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        else:
            self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
