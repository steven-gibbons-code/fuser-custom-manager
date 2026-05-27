import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QFont, QPixmapCache
from PySide6.QtWidgets import QApplication

import assets_rc  # noqa: F401 — registers Qt resources (font + icons)

QApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
)

app = QApplication(sys.argv)
# Fusion bypasses the Windows native widget renderer so QSS border-radius,
# custom backgrounds, and other properties are fully honoured.
app.setStyle("Fusion")

# Sora must be registered before any widget (including QSS) is created
QFontDatabase.addApplicationFont(":/fonts/Sora-VariableFont_wght.ttf")
app.setFont(QFont("Sora", 10))

# Pre-size the album-art gradient pixmap cache
QPixmapCache.setCacheLimit(20_000)  # KB

from gui.styles import APP_STYLE  # noqa: E402 — must come after QApplication
app.setStyleSheet(APP_STYLE)

from gui.widgets.rounded_button_filter import RoundedButtonFilter  # noqa: E402
_btn_filter = RoundedButtonFilter(app)
app.installEventFilter(_btn_filter)

from gui.main_window import FuserApp  # noqa: E402
window = FuserApp()
window.show()
sys.exit(app.exec())
