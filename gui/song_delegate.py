import re
from PySide6.QtCore import Qt, QRect, QRectF, QSize, QPointF, QModelIndex
from PySide6.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QLinearGradient,
    QPainterPath, QBrush, QPen, QPixmap, QPixmapCache,
)
from PySide6.QtWidgets import QStyledItemDelegate, QStyle

from db import ART_DIR
from gui.tokens import TOKENS, C

ROW_HEIGHT = 64
ART_SIZE   = 48
ART_RADIUS = 10
ROW_RADIUS = 14

_PALETTES = [
    (TOKENS["selection_purple"], TOKENS["accent_pink"]),
    (TOKENS["accent_pink"],      TOKENS["accent_orange"]),
    (TOKENS["stem_dj"],          TOKENS["selection_purple"]),
    (TOKENS["stem_bass"],        TOKENS["stem_synth"]),
    (TOKENS["danger"],           TOKENS["accent_orange"]),
    (TOKENS["accent_purple"],    TOKENS["accent_pink"]),
    (TOKENS["accent_orange"],    TOKENS["accent_yellow"]),
    (TOKENS["stem_dj"],          TOKENS["stem_bass"]),
]

# Module-level font cache — avoids allocating QFont objects on every paint call
_FONT_TITLE = QFont("Sora", 11)
_FONT_TITLE.setWeight(QFont.Weight.DemiBold)

_FONT_SUB = QFont("Sora", 9)
_FONT_SUB.setWeight(QFont.Weight.Medium)

_FONT_BPM = QFont("Sora", 13)
_FONT_BPM.setWeight(QFont.Weight.DemiBold)

_FONT_BPM_CAP = QFont("Sora", 8)
_FONT_BPM_CAP.setWeight(QFont.Weight.Medium)

_FONT_PILL = QFont("Sora", 8)
_FONT_PILL.setWeight(QFont.Weight.Bold)


def _rgba(token_str: str) -> QColor:
    """Parse 'rgba(r, g, b, a)' token string into QColor."""
    m = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", token_str)
    if not m:
        return QColor(token_str)
    r, g, b, a = m.groups()
    return QColor(int(r), int(g), int(b), int(float(a) * 255))


def _art_pixmap(song_id: int, size: int = ART_SIZE) -> QPixmap:
    """Return a cached pixmap for song_id: real art from disk, or gradient fallback."""
    key = f"art_{song_id}_{size}"
    pm = QPixmap()
    if QPixmapCache.find(key, pm):
        return pm

    # Check disk cache for downloaded art
    art_file = ART_DIR / f"{song_id}.jpg"
    if art_file.exists():
        source = QPixmap(str(art_file))
        if not source.isNull():
            # Scale to fill, then crop to exact square
            scaled = source.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - size) // 2
            y = (scaled.height() - size) // 2
            cropped = scaled.copy(x, y, size, size)

            # Apply rounded corners via clip path
            rounded = QPixmap(size, size)
            rounded.fill(Qt.GlobalColor.transparent)
            p = QPainter(rounded)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            clip = QPainterPath()
            clip.addRoundedRect(0, 0, size, size, ART_RADIUS, ART_RADIUS)
            p.setClipPath(clip)
            p.drawPixmap(0, 0, cropped)
            p.end()
            QPixmapCache.insert(key, rounded)
            return rounded

    # Generate gradient placeholder
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    a, b = _PALETTES[abs(song_id) % len(_PALETTES)]
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor(a))
    g.setColorAt(1, QColor(b))
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, ART_RADIUS, ART_RADIUS)
    p.fillPath(path, QBrush(g))
    p.setPen(QPen(QColor(255, 255, 255, 20), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    p.end()
    QPixmapCache.insert(key, pm)
    return pm


class SongRowDelegate(QStyledItemDelegate):
    def sizeHint(self, opt, idx) -> QSize:
        return QSize(opt.rect.width(), ROW_HEIGHT)

    def paint(self, p: QPainter, opt, idx: QModelIndex):
        song = idx.data(Qt.ItemDataRole.UserRole)
        if not song:
            return

        selected  = bool(opt.state & QStyle.StateFlag.State_Selected)
        hovered   = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        installed = bool(song.get("pak_path"))

        # Card inset: 3px top/bottom creates a 6px gap between cards
        card = QRectF(opt.rect).adjusted(0, 3, 0, -3)

        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # ── Card background ─────────────────────────────────────
        if selected:
            bg = C("surface_6")
        elif hovered:
            bg = C("surface_5")
        else:
            bg = C("surface_4")

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        card_path = QPainterPath()
        card_path.addRoundedRect(card, ROW_RADIUS, ROW_RADIUS)
        p.drawPath(card_path)

        # Green tint for installed songs
        if installed and not selected:
            p.setBrush(QColor(40, 200, 80, 75))
            p.drawPath(card_path)

        # Inner top-edge highlight
        p.setPen(QPen(QColor(255, 255, 255, 12), 1))
        p.drawLine(
            QPointF(card.left() + ROW_RADIUS, card.top() + 0.5),
            QPointF(card.right() - ROW_RADIUS, card.top() + 0.5),
        )

        # Pink rim on selected
        if selected:
            p.setPen(QPen(C("accent_pink", 0.5), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(card_path)

        # ── Install dot ─────────────────────────────────────────
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(C("success") if installed else QColor(255, 255, 255, 26))
        dot_cx = card.left() + 19
        dot_cy = card.center().y()
        p.drawEllipse(QPointF(dot_cx, dot_cy), 5, 5)

        # ── Album art ───────────────────────────────────────────
        art_x = int(card.left() + 36)
        art_y = int(card.center().y() - ART_SIZE / 2)
        p.drawPixmap(art_x, art_y, _art_pixmap(song.get("id", 0)))

        # ── Text ────────────────────────────────────────────────
        text_x    = art_x + ART_SIZE + 14
        pill_w    = 100
        bpm_w     = 70
        text_right = card.right() - pill_w - bpm_w - 28

        p.setFont(_FONT_TITLE)
        p.setPen(C("fg_white"))
        fm = QFontMetrics(_FONT_TITLE)
        title = fm.elidedText(
            song.get("title", "—"), Qt.TextElideMode.ElideRight,
            int(text_right - text_x),
        )
        p.drawText(int(text_x), int(card.top() + 24), title)

        p.setFont(_FONT_SUB)
        p.setPen(C("fg_muted"))
        bits = [song.get("artist", ""), song.get("source", ""), song.get("key", "")]
        sub = " · ".join(b for b in bits if b)
        fm = QFontMetrics(_FONT_SUB)
        sub = fm.elidedText(sub, Qt.TextElideMode.ElideRight, int(text_right - text_x))
        p.drawText(int(text_x), int(card.top() + 44), sub)

        # ── Quality pill ────────────────────────────────────────
        pill_x = card.right() - pill_w - bpm_w - 14
        pill_y = card.center().y() - 11
        self._draw_pill(p, pill_x, pill_y, pill_w, 22, song.get("quality", "Other"))

        # ── BPM block ───────────────────────────────────────────
        bpm_x = card.right() - bpm_w - 4
        p.setFont(_FONT_BPM)
        p.setPen(C("fg_white"))
        p.drawText(int(bpm_x), int(card.top() + 28), str(song.get("bpm") or "—"))
        p.setFont(_FONT_BPM_CAP)
        p.setPen(C("fg_tertiary"))
        p.drawText(int(bpm_x), int(card.top() + 44), "BPM")

        p.restore()

    def _draw_pill(self, p: QPainter, x, y, w, h, quality: str):
        bg_key, fg_key = {
            "Official":   ("tier_official_bg",   "tier_official_fg"),
            "Definitive": ("tier_definitive_bg", "tier_definitive_fg"),
            "Complete":   ("tier_complete_bg",   "tier_complete_fg"),
        }.get(quality, ("tier_other_bg", "tier_other_fg"))
        bg = _rgba(TOKENS[bg_key])
        fg = QColor(TOKENS[fg_key])
        label = quality

        path = QPainterPath()
        path.addRoundedRect(x, y, w, h, h / 2, h / 2)
        p.fillPath(path, bg)

        p.setFont(_FONT_PILL)
        p.setPen(fg)
        p.drawText(
            QRect(int(x), int(y), int(w), int(h)),
            Qt.AlignmentFlag.AlignCenter,
            label,
        )
