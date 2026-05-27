from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QProgressBar
from PySide6.QtCore import QTimer


class StatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self._lbl = QLabel("Ready")
        self._lbl.setStyleSheet("color: #666666;")
        layout.addWidget(self._lbl)
        layout.addStretch()

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setFixedWidth(200)
        self._progress.setTextVisible(False)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self.set_idle)

    def start_download(self, title: str):
        self._lbl.setText(f"Downloading: {title}")
        self._lbl.setStyleSheet("color: #e0e0e0;")
        self._progress.setValue(0)
        self._progress.show()

    def set_progress(self, value: float):
        self._progress.setValue(int(max(0.0, min(1.0, value)) * 100))

    def set_done(self, title: str):
        self._lbl.setText(f"Installed: {title}")
        self._lbl.setStyleSheet("color: #52b788;")
        self._progress.setValue(100)
        self._idle_timer.start(3000)

    def set_error(self, msg: str):
        self._lbl.setText(f"Error: {msg}")
        self._lbl.setStyleSheet("color: #e76f51;")
        self._progress.hide()

    def set_idle(self):
        self._idle_timer.stop()
        self._lbl.setText("Ready")
        self._lbl.setStyleSheet("color: #666666;")
        self._progress.hide()
        self._progress.setValue(0)

    def set_message(self, text: str):
        self._lbl.setText(text)
        self._lbl.setStyleSheet("color: #e0e0e0;")
        self._progress.hide()
