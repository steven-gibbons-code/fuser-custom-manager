APP_STYLE = """
QMainWindow, QDialog {
    background-color: #1c1c1c;
    color: #e0e0e0;
}

QWidget {
    background-color: #1c1c1c;
    color: #e0e0e0;
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}

/* ── Toolbar / filter frames ── */
QFrame#toolbar, QFrame#filterbar, QFrame#batchbar {
    background-color: #212121;
    border-bottom: 1px solid #2e2e2e;
}

/* ── Inputs ── */
QLineEdit {
    background-color: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    color: #e0e0e0;
    padding: 4px 8px;
}
QLineEdit:focus {
    border-color: #2563eb;
}
QLineEdit[placeholderText] {
    color: #555555;
}

/* ── Dropdowns ── */
QComboBox {
    background-color: #282828;
    border: 1px solid #383838;
    border-radius: 4px;
    color: #cccccc;
    padding: 4px 8px;
    min-width: 80px;
}
QComboBox:focus {
    border-color: #2563eb;
}
QComboBox::drop-down {
    border: none;
    width: 18px;
}
QComboBox::down-arrow {
    width: 8px;
    height: 8px;
    border: 2px solid #666;
    border-top: none;
    border-right: none;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #282828;
    border: 1px solid #383838;
    color: #cccccc;
    selection-background-color: #1e3a5f;
}

/* ── Buttons ── */
QPushButton {
    background-color: #2e2e2e;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    color: #bbbbbb;
    padding: 5px 12px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #383838;
    border-color: #4a4a4a;
}
QPushButton:pressed {
    background-color: #242424;
}
QPushButton:disabled {
    color: #555555;
    border-color: #2a2a2a;
}

QPushButton#primaryBtn {
    background-color: #1d4ed8;
    border-color: #2563eb;
    color: #ffffff;
}
QPushButton#primaryBtn:hover {
    background-color: #2563eb;
}
QPushButton#primaryBtn:disabled {
    background-color: #1a2a50;
    color: #555;
}

QPushButton#downloadBtn {
    background-color: #166534;
    border-color: #15803d;
    color: #86efac;
}
QPushButton#downloadBtn:hover {
    background-color: #15803d;
}
QPushButton#downloadBtn:disabled {
    background-color: #0f2a1a;
    color: #555;
}

QPushButton#dangerBtn {
    background-color: #2a2a2a;
    border-color: #3f1515;
    color: #f87171;
}
QPushButton#dangerBtn:hover {
    background-color: #3a1a1a;
}
QPushButton#dangerBtn:disabled {
    color: #555;
    border-color: #2a2a2a;
}

QPushButton#manualBtn {
    background-color: #2a2a2a;
    border-color: #3f2a00;
    color: #fbbf24;
}
QPushButton#manualBtn:hover {
    background-color: #3a2a00;
}

/* ── Table ── */
QTableView {
    background-color: #1c1c1c;
    alternate-background-color: #212121;
    border: none;
    gridline-color: transparent;
    selection-background-color: #1e3a5f;
    selection-color: #93c5fd;
    outline: none;
}
QTableView::item {
    padding: 0 6px;
    border: none;
}
QTableView::item:selected {
    background-color: #1e3a5f;
    color: #93c5fd;
}

QHeaderView::section {
    background-color: #222222;
    color: #666666;
    border: none;
    border-bottom: 2px solid #2a2a2a;
    padding: 6px 8px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── Scrollbars ── */
QScrollBar:vertical {
    background: #1c1c1c;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #3a3a3a;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #4a4a4a;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #1c1c1c;
    height: 6px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #3a3a3a;
    border-radius: 3px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Status bar ── */
QStatusBar {
    background-color: #161616;
    border-top: 1px solid #282828;
    color: #666666;
    font-size: 11px;
}
QStatusBar QLabel {
    background-color: transparent;
    padding: 0 4px;
}

QProgressBar {
    background-color: #2a2a2a;
    border: none;
    border-radius: 3px;
    max-height: 4px;
    text-visible: false;
}
QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 3px;
}

/* ── Labels ── */
QLabel#sectionTitle {
    color: #555555;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#updatedLabel {
    color: #555555;
    font-size: 11px;
}
QLabel#manualLabel {
    color: #f4a261;
}
QLabel#errorLabel {
    color: #e76f51;
}
QLabel#successLabel {
    color: #52b788;
}

/* ── Splitter ── */
QSplitter::handle {
    background-color: #2a2a2a;
    width: 1px;
}

/* ── Detail panel ── */
QFrame#detailPanel {
    background-color: #1a1a1a;
    border-left: 1px solid #272727;
}
"""
