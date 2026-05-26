import threading
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Signal

from db import get_setting, set_setting
from installer import scan_and_sync


class SettingsDialog(QDialog):
    path_saved = Signal(Path)

    def __init__(self, current_path: Path, conn, parent=None):
        super().__init__(parent)
        self._conn = conn
        self.setWindowTitle("Settings")
        self.setFixedSize(520, 200)
        self._build(current_path)

    def _build(self, current_path: Path):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        layout.addWidget(QLabel("<b>Song Install Directory</b>"))
        sub = QLabel("Choose where .pak/.sig files are installed:")
        sub.setObjectName("updatedLabel")
        layout.addWidget(sub)

        self._path_edit = QLineEdit(str(current_path))
        layout.addWidget(self._path_edit)

        btn_row = QHBoxLayout()
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        btn_row.addWidget(browse_btn)

        self._save_btn = QPushButton("Save")
        self._save_btn.setObjectName("primaryBtn")
        self._save_btn.clicked.connect(self._save)
        btn_row.addWidget(self._save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()

        layout.addLayout(btn_row)

    def _browse(self):
        chosen = QFileDialog.getExistingDirectory(
            self, "Select install directory", self._path_edit.text()
        )
        if chosen:
            self._path_edit.setText(chosen)

    def _save(self):
        new_path = Path(self._path_edit.text().strip())
        if not new_path.exists():
            reply = QMessageBox.question(
                self, "Create Directory?",
                f"Directory does not exist:\n{new_path}\n\nCreate it?",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._save_btn.setEnabled(False)
        self._save_btn.setText("Saving…")

        def _thread():
            new_path.mkdir(parents=True, exist_ok=True)
            set_setting(self._conn, "install_path", str(new_path))
            scan_and_sync(new_path, self._conn)
            self.path_saved.emit(new_path)
            self.accept()

        threading.Thread(target=_thread, daemon=True).start()
