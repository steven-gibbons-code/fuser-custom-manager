import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton
from PySide6.QtCore import Qt
from gui.refresh_mode_dialog import RefreshModeDialog

_app = QApplication.instance() or QApplication([])


def test_dialog_shows_pending_count_in_message(qtbot):
    dlg = RefreshModeDialog(pending_count=42)
    qtbot.addWidget(dlg)
    labels = dlg.findChildren(QLabel)
    assert any("42" in lbl.text() for lbl in labels)


def test_songs_art_button_accepts_dialog(qtbot):
    dlg = RefreshModeDialog(pending_count=5)
    qtbot.addWidget(dlg)
    buttons = dlg.findChildren(QPushButton)
    btn = next(b for b in buttons if b.text() == "Songs + Art")
    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
    assert dlg.result() == QDialog.DialogCode.Accepted


def test_songs_only_button_rejects_dialog(qtbot):
    dlg = RefreshModeDialog(pending_count=5)
    qtbot.addWidget(dlg)
    buttons = dlg.findChildren(QPushButton)
    btn = next(b for b in buttons if b.text() == "Songs only")
    qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
    assert dlg.result() == QDialog.DialogCode.Rejected
