from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QRect, QRectF
from PySide6.QtWidgets import QTableView, QStyledItemDelegate, QAbstractItemView, QStyle, QHeaderView
from PySide6.QtGui import QPainter, QColor, QFont, QBrush

COL_INSTALLED = 0
COL_TITLE = 1
COL_ARTIST = 2
COL_BPM = 3
COL_QUALITY = 4
COL_SOURCE = 5
NUM_COLS = 6

_HEADERS = ["", "Title", "Artist", "BPM", "Quality", "Source"]

_QUALITY_COLORS = {
    "Official":   ("#1a1535", "#8b7de8"),
    "Definitive": ("#252530", "#a0a8b8"),
    "Complete":   ("#2e2000", "#d4a017"),
    "Other":      ("#2a2a2a", "#888888"),
}


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
        return NUM_COLS

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._rows):
            return None
        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.UserRole:
            return row

        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_INSTALLED:
                return None
            if col == COL_TITLE:
                return row.get("title", "")
            if col == COL_ARTIST:
                return row.get("artist", "")
            if col == COL_BPM:
                bpm = row.get("bpm")
                return str(bpm) if bpm else ""
            if col == COL_QUALITY:
                return row.get("quality", "")
            if col == COL_SOURCE:
                return row.get("source", "")

        if role == Qt.ItemDataRole.BackgroundRole:
            if row.get("pak_path") and col != COL_INSTALLED:
                return QBrush(QColor("#152215"))

        return None

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _HEADERS[section]
        return None


class InstallDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index: QModelIndex):
        song = index.data(Qt.ItemDataRole.UserRole)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#1e3a5f"))
        else:
            bg = index.data(Qt.ItemDataRole.BackgroundRole)
            painter.fillRect(option.rect, bg.color() if bg else QColor("#1c1c1c"))
        installed = bool(song.get("pak_path")) if song else False
        cx = option.rect.center().x()
        cy = option.rect.center().y()
        radius = 4
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        if installed:
            painter.setBrush(QColor("#22c55e"))
        else:
            painter.setBrush(QColor("#3a3a3a"))
        painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
        painter.restore()


class QualityDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index: QModelIndex):
        quality = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#1e3a5f"))
        else:
            bg = index.data(Qt.ItemDataRole.BackgroundRole)
            if bg:
                painter.fillRect(option.rect, bg)
            else:
                painter.fillRect(option.rect, QColor("#1c1c1c"))
        if not quality:
            return
        bg_hex, fg_hex = _QUALITY_COLORS.get(quality, ("#2a2a2a", "#888888"))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(quality)
        badge_h = option.rect.height() - 8
        badge_w = text_width + 12
        bx = option.rect.x() + 4
        by = option.rect.y() + 4
        painter.setBrush(QColor(bg_hex))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(bx, by, badge_w, badge_h), 3, 3)
        painter.setPen(QColor(fg_hex))
        f = QFont(painter.font())
        f.setPointSize(10)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(QRect(bx, by, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, quality)
        painter.restore()


class _RowBgDelegate(QStyledItemDelegate):
    """Paints background + text directly so QSS alternate-background-color cannot override.

    initStyleOption/backgroundBrush is insufficient: QStyleSheetStyle repaints
    the alternating-row background after the brush, erasing it. Direct fillRect
    wins because it runs after all style-engine painting.
    """
    def paint(self, painter: QPainter, option, index: QModelIndex):
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor("#1e3a5f"))
        else:
            bg = index.data(Qt.ItemDataRole.BackgroundRole)
            painter.fillRect(option.rect, bg.color() if bg else QColor("#1c1c1c"))
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if text:
            painter.save()
            painter.setPen(QColor("#93c5fd") if option.state & QStyle.StateFlag.State_Selected else QColor("#e0e0e0"))
            text_rect = option.rect.adjusted(6, 0, -6, 0)
            elided = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width())
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)
            painter.restore()


class SongTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.horizontalHeader().setStretchLastSection(True)
        self.setWordWrap(False)
        self.verticalHeader().setDefaultSectionSize(28)

    def set_model(self, model: SongTableModel):
        self.setModel(model)
        self.setItemDelegateForColumn(COL_INSTALLED, InstallDelegate(self))
        self.setItemDelegateForColumn(COL_QUALITY, QualityDelegate(self))
        self.setItemDelegateForColumn(COL_TITLE, _RowBgDelegate(self))
        self.setItemDelegateForColumn(COL_ARTIST, _RowBgDelegate(self))
        self.setItemDelegateForColumn(COL_BPM, _RowBgDelegate(self))
        self.setItemDelegateForColumn(COL_SOURCE, _RowBgDelegate(self))
        self.setColumnWidth(COL_INSTALLED, 28)
        self.setColumnWidth(COL_BPM, 60)
        self.setColumnWidth(COL_QUALITY, 100)
        self.setColumnWidth(COL_SOURCE, 110)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        self.setColumnWidth(COL_ARTIST, 160)

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
