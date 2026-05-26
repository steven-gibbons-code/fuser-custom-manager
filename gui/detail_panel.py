import webbrowser
from pathlib import Path
from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QFrame,
)
from PySide6.QtCore import Signal, Qt

_FIELDS = [
    ("artist",         "Artist"),
    ("title",          "Title"),
    ("creator",        "Creator"),
    ("bpm",            "BPM"),
    ("key",            "Key"),
    ("genre",          "Genre"),
    ("year",           "Year"),
    ("submit_date",    "Date"),
    ("source",         "Source"),
    ("de_status",      "DE Status"),
    ("complete",       "Complete"),
    ("complete_notes", "Notes"),
    ("origin",         "Origin"),
    ("stream_opt",     "Stream-Opt"),
]


class DetailPanel(QScrollArea):
    download_requested = Signal(object)
    uninstall_requested = Signal(object)
    manual_install_requested = Signal(object, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._song: dict | None = None
        self.setWidgetResizable(True)
        self.setObjectName("detailPanel")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._build()

    def _build(self):
        container = QWidget()
        self.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        # Header section
        header = QFrame()
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 12)
        h_layout.setSpacing(2)
        self._title_lbl = QLabel("—")
        self._title_lbl.setStyleSheet("font-size: 16px; font-weight: 600; color: #e8e8e8;")
        self._title_lbl.setWordWrap(True)
        self._artist_lbl = QLabel("—")
        self._artist_lbl.setStyleSheet("font-size: 13px; color: #2563eb; font-weight: 500;")
        h_layout.addWidget(self._title_lbl)
        h_layout.addWidget(self._artist_lbl)
        layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #272727;")
        layout.addWidget(sep)

        # Fields section
        fields_widget = QWidget()
        fields_layout = QVBoxLayout(fields_widget)
        fields_layout.setContentsMargins(0, 8, 0, 8)
        fields_layout.setSpacing(5)

        self._labels: dict[str, QLabel] = {}
        for field, label in _FIELDS:
            if field in ("artist", "title"):
                continue
            row = QHBoxLayout()
            key_lbl = QLabel(f"{label}")
            key_lbl.setStyleSheet("font-size: 11px; color: #666; min-width: 80px;")
            key_lbl.setFixedWidth(90)
            val_lbl = QLabel("—")
            val_lbl.setStyleSheet("font-size: 12px; color: #c0c0c0;")
            val_lbl.setWordWrap(True)
            self._labels[field] = val_lbl
            row.addWidget(key_lbl)
            row.addWidget(val_lbl)
            fields_layout.addLayout(row)

        # Also add artist and title to _labels for test access
        self._labels["artist"] = self._artist_lbl
        self._labels["title"] = self._title_lbl

        # Link row
        link_row = QHBoxLayout()
        link_key = QLabel("Link")
        link_key.setStyleSheet("font-size: 11px; color: #666; min-width: 80px;")
        link_key.setFixedWidth(90)
        self._link_btn = QPushButton("—")
        self._link_btn.setFlat(True)
        self._link_btn.setStyleSheet("color: #6ab0f5; text-align: left; padding: 0;")
        self._link_btn.clicked.connect(self._open_link)
        link_row.addWidget(link_key)
        link_row.addWidget(self._link_btn)
        fields_layout.addLayout(link_row)

        self._path_lbl = QLabel("")
        self._path_lbl.setStyleSheet("font-size: 10px; color: #555; padding-top: 4px;")
        self._path_lbl.setWordWrap(True)
        fields_layout.addWidget(self._path_lbl)

        layout.addWidget(fields_widget)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #242424;")
        layout.addWidget(sep2)

        # Actions section
        actions = QWidget()
        a_layout = QVBoxLayout(actions)
        a_layout.setContentsMargins(0, 10, 0, 0)
        a_layout.setSpacing(6)

        self._dl_btn = QPushButton("Download && Install")
        self._dl_btn.setObjectName("primaryBtn")
        self._dl_btn.clicked.connect(self._download)
        a_layout.addWidget(self._dl_btn)

        self._mark_btn = QPushButton("Mark as Installed (browse .pak…)")
        self._mark_btn.setObjectName("manualBtn")
        self._mark_btn.clicked.connect(self._browse_manual_install)
        a_layout.addWidget(self._mark_btn)

        self._un_btn = QPushButton("Uninstall")
        self._un_btn.setObjectName("dangerBtn")
        self._un_btn.clicked.connect(self._uninstall)
        a_layout.addWidget(self._un_btn)

        self._manual_lbl = QLabel("")
        self._manual_lbl.setObjectName("manualLabel")
        self._manual_lbl.setWordWrap(True)
        a_layout.addWidget(self._manual_lbl)

        layout.addWidget(actions)
        layout.addStretch()

        self._sync_buttons()

    def show(self, song: dict):
        self._song = song
        self._manual_lbl.setText("")
        self._title_lbl.setText(song.get("title", "—"))
        self._artist_lbl.setText(song.get("artist", "—"))

        for field, lbl in self._labels.items():
            if field in ("artist", "title"):
                continue
            val = song.get(field)
            if field == "stream_opt":
                text = "Yes" if val else "No"
            elif field == "complete":
                text = {"D": "Definitive", "C": "Complete"}.get(str(val or ""), str(val or "—"))
            else:
                text = str(val) if val not in (None, "") else "—"
            lbl.setText(text)

        link = song.get("link", "")
        self._link_btn.setText((link[:38] + "…") if len(link) > 38 else link or "—")
        self._path_lbl.setText(
            f"Installed: {song['pak_path']}" if song.get("pak_path") else "")
        self._sync_buttons()

    def show_manual_link(self, url: str):
        self._manual_lbl.setText(
            "Manual download required.\nClick the link above to open in browser.")

    def clear(self):
        self._song = None
        self._title_lbl.setText("—")
        self._artist_lbl.setText("—")
        for field, lbl in self._labels.items():
            if field not in ("artist", "title"):
                lbl.setText("—")
        self._link_btn.setText("—")
        self._path_lbl.setText("")
        self._manual_lbl.setText("")
        self._sync_buttons()

    def _sync_buttons(self):
        if not self._song:
            self._dl_btn.setEnabled(False)
            self._mark_btn.setEnabled(False)
            self._un_btn.setEnabled(False)
            return
        installed = bool(self._song.get("pak_path"))
        self._dl_btn.setEnabled(not installed)
        self._mark_btn.setEnabled(not installed)
        self._un_btn.setEnabled(installed)

    def _open_link(self):
        if self._song:
            link = self._song.get("link", "")
            if link:
                webbrowser.open(link)

    def _download(self):
        if self._song:
            self._dl_btn.setEnabled(False)
            self.download_requested.emit(self._song)

    def _browse_manual_install(self):
        if not self._song:
            return
        self._manual_lbl.setText("")
        pak_path, _ = QFileDialog.getOpenFileName(
            self, "Select .pak file to install", "",
            "PAK files (*.pak);;All files (*.*)"
        )
        if not pak_path:
            return
        pak = Path(pak_path)
        sig_candidate = pak.with_suffix(".sig")
        sig = sig_candidate if sig_candidate.exists() else None
        self.manual_install_requested.emit(self._song, pak, sig)

    def _uninstall(self):
        if self._song:
            self.uninstall_requested.emit(self._song)
