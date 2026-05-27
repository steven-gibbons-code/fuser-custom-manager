from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QPushButton, QStyle, QStyleOptionButton
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPainterPath


class RoundedButtonFilter(QObject):
    """Application-level event filter that clips QPushButton drawing to rounded corners.

    Qt6 on Windows does not apply QSS border-radius to QPushButton even with
    Fusion style — the property is parsed but the rounded clip is never set in
    QStyleSheetStyle's CE_PushButtonBevel path.  Fixing it at the QSS level is
    impossible because the bug is inside Qt's rendering code.

    This filter intercepts each button's PaintEvent before the widget gets it,
    creates a QPainter with a rounded QPainterPath clip already in place, then
    invokes the full draw pipeline (QStyleSheetStyle → Fusion) on that painter.
    Because both style layers share our painter, ALL painting — gradient
    backgrounds, border colour, hover/pressed/disabled states — renders inside
    the rounded clip without any QSS changes.

    Install on the QApplication instance to cover every QPushButton in the app:
        _filter = RoundedButtonFilter(app)
        app.installEventFilter(_filter)
    """

    RADIUS = 22.0

    def eventFilter(self, watched, event):
        if (isinstance(watched, QPushButton) and
                event.type() == QEvent.Type.Paint):
            opt = QStyleOptionButton()
            watched.initStyleOption(opt)
            # Flat / link-style buttons have no visible background or border;
            # clipping them would do nothing and may break their transparent look.
            if not (opt.features & QStyleOptionButton.ButtonFeature.Flat):
                self._paint_rounded(watched, opt)
                return True  # Consume event — replaces default widget painting
        return False

    def _paint_rounded(self, btn: QPushButton, opt: QStyleOptionButton) -> None:
        p = QPainter(btn)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(btn.rect()), self.RADIUS, self.RADIUS)
        p.setClipPath(clip)
        # Run the full style pipeline on our clipped painter.
        # btn.style() is QStyleSheetStyle (applies QSS properties) which
        # internally delegates to Fusion — both use painter p, so both are clipped.
        btn.style().drawControl(QStyle.ControlElement.CE_PushButton, opt, p, btn)
        p.end()
