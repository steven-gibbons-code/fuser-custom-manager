from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QRadialGradient, QColor
from PySide6.QtWidgets import QWidget


class StageBackdrop(QWidget):
    """Full-window radial gradient backdrop matching the Fuser Battles screen.

    Sits as the lowest child of the central widget. All other widgets are
    transparent, allowing the gradient to show through.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.lower()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QRadialGradient(
            self.width() / 2,
            self.height() * 1.1,
            self.width() * 1.2,
        )
        g.setColorAt(0.00, QColor("#ff5e9e"))
        g.setColorAt(0.22, QColor("#6b2d7a"))
        g.setColorAt(0.50, QColor("#2a0d4a"))
        g.setColorAt(1.00, QColor("#0a0420"))
        p.fillRect(self.rect(), g)
