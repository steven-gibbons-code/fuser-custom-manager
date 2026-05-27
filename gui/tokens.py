"""Design tokens — single source of truth for all colours and gradients.

All QSS templates and paint code import from here. Never hardcode hex values
elsewhere — add a token if one is missing.
"""
from PySide6.QtGui import QColor

TOKENS = {
    # ── Surfaces ────────────────────────────────────────────────
    "surface_0":          "#0a0420",
    "surface_1":          "#150629",
    "surface_2":          "#1a0b32",
    "surface_3":          "#20133a",
    "surface_4":          "#2a1845",
    "surface_5":          "#3a205a",
    "surface_6":          "#4a2a6f",

    # ── FUSER gradient stops ───────────────────────────────────
    "accent_pink":        "#ff5e9e",
    "accent_orange":      "#ff8a5b",
    "accent_purple":      "#c14fff",
    "accent_yellow":      "#ffd166",

    # ── Solid accents ──────────────────────────────────────────
    "selection_purple":   "#5b2d8a",
    "success":            "#4ad15c",
    "warning":            "#ffb84d",
    "danger":             "#ef5350",

    # ── Stem colours ──────────────────────────────────────────
    "stem_dj":            "#4fc3f7",
    "stem_bass":          "#66bb6a",
    "stem_synth":         "#ffd54f",
    "stem_vocals":        "#ef5350",

    # ── Text ───────────────────────────────────────────────────
    "fg_white":           "#ffffff",
    "fg_soft":            "#ece4ff",
    "fg_muted":           "#b3a5d4",
    "fg_tertiary":        "#7c6aa3",
    "fg_disabled":        "#4a3a6e",

    # ── Tier pills (rgba strings for QSS; use _rgba() in paint code) ──
    "tier_official_bg":   "rgba(193, 79, 255, 0.18)",
    "tier_official_fg":   "#d29aff",
    "tier_definitive_bg": "rgba(220, 232, 255, 0.32)",
    "tier_definitive_fg": "#ffffff",
    "tier_complete_bg":   "rgba(255, 209, 102, 0.32)",
    "tier_complete_fg":   "#ffe680",
    "tier_other_bg":      "rgba(124, 106, 163, 0.18)",
    "tier_other_fg":      "#b3a5d4",
}

# QSS-syntax gradients (qlineargradient / qradialgradient, not CSS syntax)
GRADIENTS = {
    "fuser":      "qlineargradient(x1:0, y1:0.5, x2:1, y2:0.5, "
                  "stop:0 #ff5e9e, stop:1 #ff8a5b)",
    "fuser_logo": "qlineargradient(x1:0, y1:0, x2:1, y2:1, "
                  "stop:0 #c14fff, stop:0.3 #ff5e9e, "
                  "stop:0.65 #ff8a5b, stop:1 #ffd166)",
    "stage":      "qradialgradient(cx:0.5, cy:1.1, radius:1.2, "
                  "fx:0.5, fy:1.1, stop:0 #ff5e9e, stop:0.22 #6b2d7a, "
                  "stop:0.5 #2a0d4a, stop:1 #0a0420)",
}


def C(name: str, alpha: float | None = None) -> QColor:
    """Return a QColor for a hex token. Do not use with rgba() tokens."""
    c = QColor(TOKENS[name])
    if alpha is not None:
        c.setAlphaF(alpha)
    return c
