from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton


class RefreshModeDialog(QDialog):
    def __init__(self, pending_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Art sources need updating")
        self.setModal(True)
        self._build(pending_count)

    def _build(self, pending_count: int):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        msg = QLabel(
            f"{pending_count} songs are missing art URLs. Resolving these requires\n"
            "MusicBrainz lookups (1 req/sec) and may scrape a large\n"
            "Google Drive index. This can take several minutes."
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)

        songs_art_btn = QPushButton("Songs + Art")
        songs_art_btn.setObjectName("primaryBtn")
        songs_art_btn.clicked.connect(self.accept)
        buttons.addWidget(songs_art_btn)

        songs_only_btn = QPushButton("Songs only")
        songs_only_btn.clicked.connect(self.reject)
        buttons.addWidget(songs_only_btn)

        layout.addLayout(buttons)
