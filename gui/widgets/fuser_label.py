from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import (
    QPainter, QLinearGradient, QFont, QColor,
    QPainterPath, QFontMetricsF,
)
from PySide6.QtWidgets import QWidget

from gui.tokens import TOKENS


class FuserLabel(QWidget):
    """FUSER logotype rendered with a multi-stop gradient fill.

    QSS cannot do background-clip:text, so we override paintEvent and fill
    a QPainterPath with a QLinearGradient. The same widget renders any text
    in the FUSER gradient; default is "FUSER".
    """

    def __init__(self, text: str = "FUSER", pt_size: int = 40, parent=None):
        super().__init__(parent)
        self._text = text
        self._pt_size = pt_size
        f = QFont("Sora", pt_size)
        f.setWeight(QFont.Weight.Black)
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 104)
        self._font = f
        # WA_TranslucentBackground enables OS-level compositing so the gradient
        # path renders over the StageBackdrop without a solid widget background.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def setText(self, text: str):
        self._text = text
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        fm = QFontMetricsF(self._font)
        return QSize(int(fm.horizontalAdvance(self._text) + 12),
                     int(fm.height() + 12))

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )
        rect = QRectF(self.rect()).adjusted(6, 6, -6, -6)

        # 4-stop gradient: purple → pink → orange → yellow
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.00, QColor(TOKENS["accent_purple"]))
        grad.setColorAt(0.30, QColor(TOKENS["accent_pink"]))
        grad.setColorAt(0.65, QColor(TOKENS["accent_orange"]))
        grad.setColorAt(1.00, QColor(TOKENS["accent_yellow"]))

        path = QPainterPath()
        path.addText(
            rect.left(),
            rect.top() + QFontMetricsF(self._font).ascent(),
            self._font,
            self._text,
        )

        # Soft glow: 8 offset copies in semi-transparent pink before the fill
        glow = QColor(255, 94, 158, 110)
        p.save()
        p.translate(0, 2)
        p.setBrush(glow)
        p.setPen(Qt.PenStyle.NoPen)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (1, 1), (-1, 1), (1, -1)]:
            p.translate(dx, dy)
            p.drawPath(path)
            p.translate(-dx, -dy)
        p.restore()

        # Gradient fill
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)
