from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QFrame,
)
from PySide6.QtCore import Signal, Qt

_SORT_MAP = {
    "Artist A–Z":   ("s.artist",      False),
    "Newest First": ("s.submit_date", True),
    "BPM ↑":        ("s.bpm",         False),
    "BPM ↓":        ("s.bpm",         True),
}

_INSTALLED_MAP = {
    "Installed":     "installed",
    "Not Installed": "not_installed",
}


class FilterBar(QWidget):
    filters_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()
        self._connect()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Row 1: search + actions ──
        top = QFrame()
        top.setObjectName("toolbar")
        self._top_layout = QHBoxLayout(top)
        top_layout = self._top_layout
        top_layout.setContentsMargins(8, 6, 8, 6)
        top_layout.setSpacing(6)

        top_layout.addWidget(QLabel("Search"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Artist, title, genre…")
        self._search.setFixedWidth(240)
        top_layout.addWidget(self._search)
        top_layout.addStretch()

        self._updated_lbl = QLabel("")
        self._updated_lbl.setObjectName("updatedLabel")
        top_layout.addWidget(self._updated_lbl)

        self._refresh_btn = QPushButton("Refresh Sources")
        self._refresh_btn.setObjectName("primaryBtn")
        top_layout.addWidget(self._refresh_btn)

        self._settings_btn = QPushButton("⚙ Settings")
        top_layout.addWidget(self._settings_btn)

        outer.addWidget(top)

        # ── Row 2: filters ──
        fbar = QFrame()
        fbar.setObjectName("filterbar")
        fbar_layout = QHBoxLayout(fbar)
        fbar_layout.setContentsMargins(8, 4, 8, 4)
        fbar_layout.setSpacing(4)

        fbar_layout.addWidget(QLabel("Source"))
        self._source = QComboBox()
        self._source.addItems(["All Sources", "fucuco_main", "fucuco_vgm", "fusersoundlab"])
        fbar_layout.addWidget(self._source)

        fbar_layout.addWidget(QLabel("Quality"))
        self._quality = QComboBox()
        self._quality.addItems(["All Quality", "Official", "Definitive", "Complete", "Other"])
        fbar_layout.addWidget(self._quality)

        fbar_layout.addWidget(QLabel("Status"))
        self._installed = QComboBox()
        self._installed.addItems(["All", "Installed", "Not Installed"])
        fbar_layout.addWidget(self._installed)

        fbar_layout.addWidget(QLabel("Genre"))
        self._genre = QLineEdit()
        self._genre.setPlaceholderText("e.g. Rock")
        self._genre.setFixedWidth(90)
        fbar_layout.addWidget(self._genre)

        fbar_layout.addWidget(QLabel("BPM"))
        self._bpm_min = QLineEdit()
        self._bpm_min.setPlaceholderText("min")
        self._bpm_min.setFixedWidth(52)
        fbar_layout.addWidget(self._bpm_min)
        fbar_layout.addWidget(QLabel("–"))
        self._bpm_max = QLineEdit()
        self._bpm_max.setPlaceholderText("max")
        self._bpm_max.setFixedWidth(52)
        fbar_layout.addWidget(self._bpm_max)

        fbar_layout.addWidget(QLabel("Sort"))
        self._sort = QComboBox()
        self._sort.addItems(["Artist A–Z", "Newest First", "BPM ↑", "BPM ↓"])
        fbar_layout.addWidget(self._sort)

        fbar_layout.addStretch()

        clear_btn = QPushButton("✕ Clear Filters")
        clear_btn.clicked.connect(self.clear)
        fbar_layout.addWidget(clear_btn)

        outer.addWidget(fbar)

    def _connect(self):
        self._search.textChanged.connect(self._emit)
        self._source.currentIndexChanged.connect(self._emit)
        self._quality.currentIndexChanged.connect(self._emit)
        self._installed.currentIndexChanged.connect(self._emit)
        self._genre.textChanged.connect(self._emit)
        self._bpm_min.textChanged.connect(self._emit)
        self._bpm_max.textChanged.connect(self._emit)
        self._sort.currentIndexChanged.connect(self._emit)

    def _emit(self):
        self.filters_changed.emit(self.get_filters())

    def get_filters(self) -> dict:
        f: dict = {"search": self._search.text()}

        src = self._source.currentText()
        if src != "All Sources":
            f["source"] = src

        q = self._quality.currentText()
        if q != "All Quality":
            f["quality"] = q

        installed_val = _INSTALLED_MAP.get(self._installed.currentText())
        if installed_val:
            f["installed"] = installed_val

        genre = self._genre.text().strip()
        if genre:
            f["genre"] = genre

        try:
            if self._bpm_min.text():
                f["bpm_min"] = int(self._bpm_min.text())
        except ValueError:
            pass
        try:
            if self._bpm_max.text():
                f["bpm_max"] = int(self._bpm_max.text())
        except ValueError:
            pass

        order_by, descending = _SORT_MAP.get(self._sort.currentText(), ("s.artist", False))
        f["order_by"] = order_by
        if descending:
            f["descending"] = True

        return f

    def clear(self):
        for widget in (self._search, self._genre, self._bpm_min, self._bpm_max):
            widget.blockSignals(True)
            widget.clear()
            widget.blockSignals(False)
        for combo in (self._source, self._quality, self._installed, self._sort):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self._emit()

    def add_to_toolbar(self, widget):
        """Append a widget to the right end of the top toolbar row."""
        self._top_layout.addWidget(widget)

    def prepend_to_toolbar(self, widget):
        """Insert a widget at position 0 of the top toolbar row."""
        self._top_layout.insertWidget(0, widget)

    def set_updated_label(self, text: str):
        self._updated_lbl.setText(text)

    def set_refresh_enabled(self, enabled: bool):
        self._refresh_btn.setEnabled(enabled)
        self._refresh_btn.setText("Refreshing…" if not enabled else "Refresh Sources")
