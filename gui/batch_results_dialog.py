from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget,
)
from PySide6.QtCore import Signal, Qt

_ICONS = {"ok": "✓", "manual": "⚠", "error": "✗", "skipped": "—"}
_COLORS = {
    "ok":      "#52b788",
    "manual":  "#f4a261",
    "error":   "#e76f51",
    "skipped": "#888888",
}


class BatchResultsDialog(QDialog):
    closed = Signal()

    def __init__(self, results: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Download Results")
        self.resize(600, 420)
        self._build(results)

    def _build(self, results: list[dict]):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        ok_count = sum(1 for r in results if r["status"] == "ok")
        total = len(results)
        summary_color = "#52b788" if ok_count == total else "#f4a261"
        summary = QLabel(f"Batch Download — {ok_count} of {total} succeeded")
        summary.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {summary_color};"
        )
        layout.addWidget(summary)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(4, 4, 4, 4)
        inner_layout.setSpacing(4)

        for entry in results:
            song = entry["song"]
            status = entry["status"]
            msg = entry.get("message", "")
            icon = _ICONS.get(status, "?")
            color = _COLORS.get(status, "white")

            row = QHBoxLayout()
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(f"color: {color}; font-size: 13px; min-width: 16px;")
            icon_lbl.setFixedWidth(20)
            title_lbl = QLabel(song.get("title", "?"))
            title_lbl.setStyleSheet("font-size: 12px;")
            msg_lbl = QLabel(msg)
            msg_lbl.setStyleSheet("font-size: 11px; color: #888;")

            row.addWidget(icon_lbl)
            row.addWidget(title_lbl)
            row.addStretch()
            row.addWidget(msg_lbl)
            inner_layout.addLayout(row)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self._on_close)
        layout.addWidget(close_btn)

    def _on_close(self):
        self.closed.emit()
        self.accept()
