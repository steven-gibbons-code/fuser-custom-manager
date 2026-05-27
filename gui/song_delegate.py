import re
from PySide6.QtCore import Qt, QRect, QRectF, QSize, QPointF, QModelIndex
from PySide6.QtGui import (
    QPainter, QColor, QFont, QFontMetrics, QLinearGradient,
    QPainterPath, QBrush, QPen, QPixmap, QPixmapCache,
)
from PySide6.QtWidgets import QStyledItemDelegate, QStyle

from gui.tokens import TOKENS, C

ROW_HEIGHT = 64
ART_SIZE   = 48
ART_RADIUS = 10
ROW_RADIUS = 14

_PALETTES = [
    ("#5b2d8a", "#ff5e9e"),
    ("#ff5e9e", "#ff8a5b"),
    ("#4fc3f7", "#5b2d8a"),
    ("#66bb6a", "#ffd54f"),
    ("#ef5350", "#ff8a5b"),
    ("#c14fff", "#ff5e9e"),
    ("#ff8a5b", "#ffd54f"),
    ("#4fc3f7", "#66bb6a"),
]


def _rgba(token_str: str) -> QColor:
    """Parse 'rgba(r, g, b, a)' token string into QColor."""
    m = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", token_str)
    if not m:
        return QColor(token_str)
    r, g, b, a = m.groups()
    return QColor(int(r), int(g), int(b), int(float(a) * 255))


def _art_pixmap(song_id: int, size: int = ART_SIZE) -> QPixmap:
    """Return a cached gradient album-art square for the given song id."""
    key = f"art_{song_id}_{size}"
    pm = QPixmap()
    if not QPixmapCache.find(key, pm):
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

        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        hovered  = bool(opt.state & QStyle.StateFlag.State_MouseOver)

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
        installed = bool(song.get("pak_path"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(C("success") if installed else QColor(255, 255, 255, 26))
        dot_cx = card.left() + 19
        dot_cy = card.center().y()
        p.drawEllipse(QPointF(dot_cx, dot_cy), 5, 5)

        # ── Album art ───────────────────────────────────────────
        art_x = int(card.left() + 36)
        art_y = int(card.center().y() - ART_SIZE / 2)
        p.drawPixmap(art_x, art_y, _art_pixmap(song["id"]))

        # ── Text ────────────────────────────────────────────────
        text_x    = art_x + ART_SIZE + 14
        pill_w    = 100
        bpm_w     = 70
        text_right = card.right() - pill_w - bpm_w - 28

        title_font = QFont("Sora", 11)
        title_font.setWeight(QFont.Weight.DemiBold)
        p.setFont(title_font)
        p.setPen(C("fg_white"))
        fm = QFontMetrics(title_font)
        title = fm.elidedText(
            song.get("title", "—"), Qt.TextElideMode.ElideRight,
            int(text_right - text_x),
        )
        p.drawText(int(text_x), int(card.top() + 24), title)

        sub_font = QFont("Sora", 9)
        sub_font.setWeight(QFont.Weight.Medium)
        p.setFont(sub_font)
        p.setPen(C("fg_muted"))
        bits = [song.get("artist", ""), song.get("source", ""), song.get("key", "")]
        sub = " · ".join(b for b in bits if b)
        fm = QFontMetrics(sub_font)
        sub = fm.elidedText(sub, Qt.TextElideMode.ElideRight, int(text_right - text_x))
        p.drawText(int(text_x), int(card.top() + 44), sub)

        # ── Quality pill ────────────────────────────────────────
        pill_x = card.right() - pill_w - bpm_w - 14
        pill_y = card.center().y() - 11
        self._draw_pill(p, pill_x, pill_y, pill_w, 22,
                        song.get("quality", "Other"), installed)

        # ── BPM block ───────────────────────────────────────────
        bpm_x = card.right() - bpm_w - 4
        big = QFont("Sora", 13)
        big.setWeight(QFont.Weight.DemiBold)
        p.setFont(big)
        p.setPen(C("fg_white"))
        p.drawText(int(bpm_x), int(card.top() + 28), str(song.get("bpm") or "—"))
        cap = QFont("Sora", 8)
        cap.setWeight(QFont.Weight.Medium)
        p.setFont(cap)
        p.setPen(C("fg_tertiary"))
        p.drawText(int(bpm_x), int(card.top() + 44), "BPM")

        p.restore()

    def _draw_pill(self, p: QPainter, x, y, w, h, quality: str, installed: bool):
        if installed:
            bg = _rgba("rgba(74, 209, 92, 0.18)")
            fg = QColor("#7be089")
            label = f"✓ {quality}"
        else:
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

        f = QFont("Sora", 8)
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(fg)
        p.drawText(
            QRect(int(x), int(y), int(w), int(h)),
            Qt.AlignmentFlag.AlignCenter,
            label,
        )
