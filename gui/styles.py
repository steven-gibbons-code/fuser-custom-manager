from gui.tokens import TOKENS, GRADIENTS

APP_STYLE = """
QMainWindow, QDialog {{
    background: {surface_2};
    color: {fg_soft};
    font-family: "Sora";
    font-size: 14px;
}}

QWidget {{
    background: transparent;
    color: {fg_soft};
    font-family: "Sora";
    font-size: 14px;
}}

/* ── Toolbar / filter frames ── */
QFrame#toolbar, QFrame#filterbar, QFrame#batchbar {{
    background: rgba(10, 4, 32, 0.5);
    border-bottom: 1px solid rgba(255,255,255,0.04);
}}

QFrame#toolbar QLabel, QFrame#filterbar QLabel {{
    color: {fg_tertiary};
    font-size: 12px;
    background: transparent;
}}

/* ── Inputs ── */
QLineEdit {{
    background: {surface_1};
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 0 18px;
    color: {fg_white};
    min-height: 34px;
    font-size: 13px;
}}
QLineEdit:focus {{
    border-color: {accent_pink};
}}

/* ── Dropdowns ── */
QComboBox {{
    background: {surface_2};
    color: {fg_soft};
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 18px;
    padding: 6px 28px 6px 14px;
    font-size: 13px;
    min-height: 28px;
}}
QComboBox:focus {{
    border-color: {accent_pink};
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0;
    height: 0;
}}
QComboBox QAbstractItemView {{
    background: {surface_2};
    border: 1px solid rgba(255,255,255,0.08);
    color: {fg_soft};
    selection-background-color: {selection_purple};
}}

/* ── Buttons ── */
QPushButton {{
    background: {surface_2};
    color: {fg_soft};
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 22px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    min-height: 24px;
}}
QPushButton:hover {{
    background: {surface_3};
    border-color: rgba(255,255,255,0.18);
}}
QPushButton:pressed {{
    background: {surface_1};
}}
QPushButton:disabled {{
    color: {fg_disabled};
    border-color: rgba(255,255,255,0.04);
}}

QPushButton#primaryBtn {{
    background: {fuser};
    color: white;
    border: 1px solid rgba(255,255,255,0.06);
}}
QPushButton#primaryBtn:hover {{
    background: {fuser};
    border-color: rgba(255,255,255,0.2);
}}
QPushButton#primaryBtn:disabled {{
    background: {surface_1};
    color: {fg_disabled};
}}

QPushButton#downloadBtn {{
    background: transparent;
    color: {success};
    border: 1px solid rgba(74,209,92,0.4);
}}
QPushButton#downloadBtn:hover {{
    background: rgba(74,209,92,0.1);
}}
QPushButton#downloadBtn:disabled {{
    color: {fg_disabled};
    border-color: rgba(255,255,255,0.04);
}}

QPushButton#dangerBtn {{
    background: transparent;
    color: {danger};
    border: 1px solid rgba(239,83,80,0.4);
}}
QPushButton#dangerBtn:hover {{
    background: rgba(239,83,80,0.1);
}}
QPushButton#dangerBtn:disabled {{
    color: {fg_disabled};
    border-color: rgba(255,255,255,0.04);
}}

QPushButton#manualBtn {{
    background: transparent;
    color: {warning};
    border: 1px solid rgba(255,184,77,0.4);
}}
QPushButton#manualBtn:hover {{
    background: rgba(255,184,77,0.1);
}}
QPushButton#manualBtn:disabled {{
    color: {fg_disabled};
    border-color: rgba(255,255,255,0.04);
}}

/* ── Table ── */
QTableView {{
    background: transparent;
    selection-background-color: transparent;
    selection-color: {fg_white};
    border: none;
    gridline-color: transparent;
    outline: 0;
}}
QTableView::item {{
    padding: 0;
    border: none;
}}
QTableView::item:selected {{
    background: transparent;
    color: {fg_white};
}}

QHeaderView::section {{
    background: transparent;
    color: {fg_tertiary};
    border: 0;
    padding: 8px 14px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}}

/* ── Scrollbars ── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,0.1);
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(255,255,255,0.2);
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: rgba(255,255,255,0.1);
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: rgba(255,255,255,0.2);
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Status bar ── */
QStatusBar {{
    background: rgba(10,4,32,0.6);
    color: {fg_soft};
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 22px;
    font-size: 13px;
    min-height: 36px;
    margin: 4px 8px;
}}
QStatusBar QLabel {{
    background: transparent;
    padding: 0 4px;
}}

QProgressBar {{
    background: rgba(255,255,255,0.06);
    border: none;
    border-radius: 3px;
    max-height: 4px;
    text-visible: 0;
}}
QProgressBar::chunk {{
    background: {fuser};
    border-radius: 3px;
}}

/* ── Labels ── */
QLabel#sectionTitle {{
    color: {fg_tertiary};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
}}
QLabel#updatedLabel {{
    color: {fg_tertiary};
    font-size: 11px;
}}
QLabel#manualLabel {{
    color: {warning};
}}
QLabel#errorLabel {{
    color: {danger};
}}
QLabel#successLabel {{
    color: {success};
}}

/* ── Splitter ── */
QSplitter::handle {{
    background: rgba(255,255,255,0.04);
    width: 1px;
}}

/* ── Detail panel ── */
QFrame#detailPanel {{
    background: {surface_2};
    border-radius: 20px;
    border: 1px solid rgba(255,255,255,0.05);
}}
""".format(**TOKENS, **GRADIENTS)
