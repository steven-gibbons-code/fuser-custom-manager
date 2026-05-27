import webbrowser
from pathlib import Path
from PySide6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QFrame,
)
from PySide6.QtCore import Signal, Qt, QTimer

from gui.tokens import TOKENS
from gui.song_delegate import _art_pixmap
from db import ART_DIR

_FIELDS = [
    ("creator",        "Creator"),
    ("genre",          "Genre"),
    ("year",           "Year"),
    ("submit_date",    "Date"),
    ("source",         "Source"),
    ("de_status",      "DE Status"),
    ("complete",       "Complete"),
    ("complete_notes", "Notes"),
    ("origin",         "Origin"),
    ("stream_opt",     "Stream-Opt"),
]

_TIER_PILL = {
    "Official":   (TOKENS["tier_official_bg"],   TOKENS["tier_official_fg"]),
    "Definitive": (TOKENS["tier_definitive_bg"],  TOKENS["tier_definitive_fg"]),
    "Complete":   (TOKENS["tier_complete_bg"],    TOKENS["tier_complete_fg"]),
}
_MUTED_PILL_BG = TOKENS["pill_muted_bg"]
_MUTED_PILL_FG = TOKENS["fg_muted"]


def _pill_style(bg: str, fg: str) -> str:
    return (
        f"background: {bg}; color: {fg}; border-radius: 11px; "
        f"padding: 3px 11px; font-size: 12px; font-weight: 600;"
    )


class DetailPanel(QScrollArea):
    download_requested = Signal(object)
    uninstall_requested = Signal(object)
    manual_install_requested = Signal(object, object, object)
    fetch_art_requested = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._song: dict | None = None
        self.setWidgetResizable(True)
        self.setObjectName("detailPanel")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._build()

    def _build(self):
        container = QWidget()
        self.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)

        # ── Album art ──────────────────────────────────────────────
        self._art_lbl = QLabel()
        self._art_lbl.setFixedSize(160, 160)
        self._art_lbl.setStyleSheet("border-radius: 14px; background: transparent;")
        self._art_lbl.setPixmap(_art_pixmap(0, size=160))
        layout.addWidget(self._art_lbl)

        self._art_overlay_btn = QPushButton("↓", self._art_lbl)
        self._art_overlay_btn.setGeometry(58, 58, 44, 44)
        self._art_overlay_btn.setStyleSheet(
            "background: rgba(0,0,0,0.55); color: white; border-radius: 22px; "
            "font-size: 20px; border: none;"
        )
        self._art_overlay_btn.clicked.connect(self._on_fetch_art_clicked)
        self._art_overlay_btn.hide()

        self._art_spinner_lbl = QLabel("⠋", self._art_lbl)
        self._art_spinner_lbl.setGeometry(58, 58, 44, 44)
        self._art_spinner_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._art_spinner_lbl.setStyleSheet(
            "background: rgba(0,0,0,0.55); color: white; border-radius: 22px; font-size: 16px;"
        )
        self._art_spinner_lbl.hide()

        self._spinner_frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self._spinner_idx = 0
        self._spinner_timer = QTimer(self)
        self._spinner_timer.setInterval(100)
        self._spinner_timer.timeout.connect(self._tick_spinner)

        layout.addSpacing(14)

        # ── Title ──────────────────────────────────────────────────
        self._title_lbl = QLabel("—")
        self._title_lbl.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {TOKENS['fg_white']}; "
            f"background: transparent;"
        )
        self._title_lbl.setWordWrap(True)
        layout.addWidget(self._title_lbl)
        layout.addSpacing(2)

        # ── Artist ─────────────────────────────────────────────────
        self._artist_lbl = QLabel("—")
        self._artist_lbl.setStyleSheet(
            f"font-size: 14px; color: {TOKENS['accent_pink']}; "
            f"font-weight: 500; background: transparent;"
        )
        layout.addWidget(self._artist_lbl)
        layout.addSpacing(12)

        # ── Pills: Quality | Key | BPM ──────────────────────────────
        pills_row = QHBoxLayout()
        pills_row.setSpacing(6)
        pills_row.setContentsMargins(0, 0, 0, 0)

        self._quality_pill = QLabel("—")
        self._quality_pill.setStyleSheet(_pill_style(_MUTED_PILL_BG, _MUTED_PILL_FG))
        pills_row.addWidget(self._quality_pill)

        self._key_pill = QLabel("—")
        self._key_pill.setStyleSheet(_pill_style(_MUTED_PILL_BG, _MUTED_PILL_FG))
        pills_row.addWidget(self._key_pill)

        self._bpm_pill = QLabel("—")
        self._bpm_pill.setStyleSheet(_pill_style(_MUTED_PILL_BG, _MUTED_PILL_FG))
        pills_row.addWidget(self._bpm_pill)

        pills_row.addStretch()
        layout.addLayout(pills_row)
        layout.addSpacing(14)

        # ── Separator ──────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.06);")
        layout.addWidget(sep)

        # ── Fields ─────────────────────────────────────────────────
        fields_widget = QWidget()
        fields_layout = QVBoxLayout(fields_widget)
        fields_layout.setContentsMargins(0, 10, 0, 10)
        fields_layout.setSpacing(6)

        self._labels: dict[str, QLabel] = {}
        for field, label in _FIELDS:
            row = QHBoxLayout()
            row.setSpacing(8)
            key_lbl = QLabel(label.upper())
            key_lbl.setStyleSheet(
                f"font-size: 10px; color: {TOKENS['fg_tertiary']}; "
                f"font-weight: 600; background: transparent;"
            )
            key_lbl.setFixedWidth(84)
            val_lbl = QLabel("—")
            val_lbl.setStyleSheet(
                f"font-size: 13px; color: {TOKENS['fg_soft']}; background: transparent;"
            )
            val_lbl.setWordWrap(True)
            self._labels[field] = val_lbl
            row.addWidget(key_lbl)
            row.addWidget(val_lbl)
            fields_layout.addLayout(row)

        # Link row
        link_row = QHBoxLayout()
        link_row.setSpacing(8)
        link_key = QLabel("LINK")
        link_key.setStyleSheet(
            f"font-size: 10px; color: {TOKENS['fg_tertiary']}; "
            f"font-weight: 600; background: transparent;"
        )
        link_key.setFixedWidth(84)
        self._link_btn = QPushButton("—")
        self._link_btn.setFlat(True)
        self._link_btn.setStyleSheet(
            f"color: {TOKENS['accent_pink']}; text-align: left; "
            f"padding: 0; background: transparent; border: none; font-size: 13px;"
        )
        self._link_btn.clicked.connect(self._open_link)
        link_row.addWidget(link_key)
        link_row.addWidget(self._link_btn)
        fields_layout.addLayout(link_row)

        self._path_lbl = QLabel("")
        self._path_lbl.setStyleSheet(
            f"font-size: 10px; color: {TOKENS['fg_disabled']}; "
            f"padding-top: 4px; background: transparent;"
        )
        self._path_lbl.setWordWrap(True)
        fields_layout.addWidget(self._path_lbl)

        # Also expose title/artist in _labels for test access
        self._labels["artist"] = self._artist_lbl
        self._labels["title"] = self._title_lbl

        layout.addWidget(fields_widget)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: rgba(255,255,255,0.06);")
        layout.addWidget(sep2)

        # ── Actions ────────────────────────────────────────────────
        actions = QWidget()
        a_layout = QVBoxLayout(actions)
        a_layout.setContentsMargins(0, 10, 0, 0)
        a_layout.setSpacing(6)

        self._dl_btn = QPushButton("Download & Install")
        self._dl_btn.setObjectName("primaryBtn")
        self._dl_btn.clicked.connect(self._download)
        a_layout.addWidget(self._dl_btn)

        self._mark_btn = QPushButton("Mark as Installed (browse .pak…)")
        self._mark_btn.setObjectName("manualBtn")
        self._mark_btn.clicked.connect(self._browse_manual_install)
        a_layout.addWidget(self._mark_btn)

        self._un_btn = QPushButton("Uninstall")
        self._un_btn.setObjectName("dangerBtn")
        self._un_btn.clicked.connect(self._uninstall)
        a_layout.addWidget(self._un_btn)

        self._manual_lbl = QLabel("")
        self._manual_lbl.setObjectName("manualLabel")
        self._manual_lbl.setWordWrap(True)
        a_layout.addWidget(self._manual_lbl)

        layout.addWidget(actions)
        layout.addStretch()

        self._sync_buttons()

    def _update_art_overlay(self):
        if not self._song:
            self._art_overlay_btn.hide()
            self._art_spinner_lbl.hide()
            self._spinner_timer.stop()
            return
        has_art = (ART_DIR / f"{self._song['id']}.jpg").exists()
        self._art_overlay_btn.setVisible(not has_art)
        if has_art:
            self._art_spinner_lbl.hide()
            self._spinner_timer.stop()

    def _on_fetch_art_clicked(self):
        self._art_overlay_btn.hide()
        self._art_spinner_lbl.show()
        self._spinner_timer.start()
        self.fetch_art_requested.emit(self._song)

    def _tick_spinner(self):
        self._spinner_idx = (self._spinner_idx + 1) % len(self._spinner_frames)
        self._art_spinner_lbl.setText(self._spinner_frames[self._spinner_idx])

    def show(self, song: dict):
        super().show()
        self._song = song
        self._manual_lbl.setText("")

        self._art_lbl.setPixmap(_art_pixmap(song.get("id", 0), size=160))
        self._title_lbl.setText(song.get("title", "—"))
        self._artist_lbl.setText(song.get("artist", "—"))

        # Quality pill — always tier-coloured
        quality = song.get("quality", "Other") or "Other"
        q_bg, q_fg = _TIER_PILL.get(quality, (TOKENS["tier_other_bg"], TOKENS["tier_other_fg"]))
        self._quality_pill.setStyleSheet(_pill_style(q_bg, q_fg))
        self._quality_pill.setText(quality)

        key = song.get("key", "") or ""
        self._key_pill.setText(key if key else "—")

        bpm = song.get("bpm")
        self._bpm_pill.setText(f"{bpm} BPM" if bpm else "—")

        for field, lbl in self._labels.items():
            if field in ("artist", "title"):
                continue
            val = song.get(field)
            if field == "stream_opt":
                text = "Yes" if val else "No"
            elif field == "complete":
                text = {"D": "Definitive", "C": "Complete"}.get(str(val or ""), str(val or "—"))
            else:
                text = str(val) if val not in (None, "") else "—"
            lbl.setText(text)

        link = song.get("link", "")
        self._link_btn.setText((link[:38] + "…") if len(link) > 38 else link or "—")
        self._path_lbl.setText(
            f"Installed: {song['pak_path']}" if song.get("pak_path") else ""
        )
        self._sync_buttons()
        self._update_art_overlay()

    def show_manual_link(self, url: str):
        self._manual_lbl.setText(
            "Manual download required.\nClick the link above to open in browser."
        )

    def clear(self):
        self._song = None
        self._art_lbl.setPixmap(_art_pixmap(0, size=160))
        self._title_lbl.setText("—")
        self._artist_lbl.setText("—")
        self._quality_pill.setText("—")
        self._quality_pill.setStyleSheet(_pill_style(_MUTED_PILL_BG, _MUTED_PILL_FG))
        self._key_pill.setText("—")
        self._bpm_pill.setText("—")
        for field, lbl in self._labels.items():
            if field not in ("artist", "title"):
                lbl.setText("—")
        self._link_btn.setText("—")
        self._path_lbl.setText("")
        self._manual_lbl.setText("")
        self._sync_buttons()
        self._update_art_overlay()

    def _sync_buttons(self):
        if not self._song:
            self._dl_btn.setEnabled(False)
            self._mark_btn.setEnabled(False)
            self._un_btn.setEnabled(False)
            return
        installed = bool(self._song.get("pak_path"))
        self._dl_btn.setEnabled(not installed)
        self._mark_btn.setEnabled(not installed)
        self._un_btn.setEnabled(installed)

    def _open_link(self):
        if self._song:
            link = self._song.get("link", "")
            if link:
                webbrowser.open(link)

    def _download(self):
        if self._song:
            self._dl_btn.setEnabled(False)
            self.download_requested.emit(self._song)

    def _browse_manual_install(self):
        if not self._song:
            return
        self._manual_lbl.setText("")
        pak_path, _ = QFileDialog.getOpenFileName(
            self, "Select .pak file to install", "",
            "PAK files (*.pak);;All files (*.*)"
        )
        if not pak_path:
            return
        pak = Path(pak_path)
        sig_candidate = pak.with_suffix(".sig")
        sig = sig_candidate if sig_candidate.exists() else None
        self.manual_install_requested.emit(self._song, pak, sig)

    def _uninstall(self):
        if self._song:
            self.uninstall_requested.emit(self._song)
