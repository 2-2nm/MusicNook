from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QRadialGradient

from ui import theme

# Where the cover-colour glow sits. The player page uses a round spotlight; the Library uses a wide glow that
# is anchored on the Continue listening card at the top. paint_backdrop blends the two with `mode`.
#            centre x, centre y (fractions of the window), radius x (fraction of w), radius y (fraction of h)
LIBRARY_GLOW = (0.38, 0.17, 0.62, 0.42)
PLAYER_GLOW = (0.30, 0.40, None, None)  # radius = 0.55 * max(w, h), round
LIBRARY_GLOW2 = (0.92, 0.12, 0.30)      # second hue: top right, next to "Recently added"
PLAYER_GLOW2 = (0.85, 0.95, 0.40)       # second hue: bottom right
LIBRARY_ALPHA, PLAYER_ALPHA = 140, 150


def _mix(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _glow(p, cx, cy, rx, ry, color: QColor, alpha: float, w: int, h: int):
    """Elliptical radial glow: strongest in the centre, fully transparent at the edge."""
    c = QColor(color)
    c.setAlpha(max(0, min(255, int(alpha))))
    p.save()
    p.translate(cx, cy)
    p.scale(1.0, ry / rx)  # a circle squashed into an ellipse
    g = QRadialGradient(0, 0, rx)
    g.setColorAt(0, c)
    c.setAlpha(0)
    g.setColorAt(1, c)
    p.fillRect(QRectF(-cx, -cy * rx / ry, w, h * rx / ry), g)
    p.restore()


def paint_backdrop(p, w: int, h: int, tint=None, mode: float = 1.0, strength: float = 1.0):
    """Window background. `tint` is the cover colour; `mode` 0 = Library pattern, 1 = player pattern (values in
    between blend the two, so changing page glides); `strength` fades the whole tint in or out."""
    p.fillRect(0, 0, w, h, QColor(theme.BG))
    g = QRadialGradient(w * 0.12, 0, w * 0.75)
    g.setColorAt(0, QColor(32, 52, 170, 230))
    g.setColorAt(1, QColor(32, 52, 170, 0))
    p.fillRect(0, 0, w, h, g)
    g2 = QRadialGradient(w, h, w * 0.55)
    g2.setColorAt(0, QColor(110, 40, 160, 150))
    g2.setColorAt(1, QColor(110, 40, 160, 0))
    p.fillRect(0, 0, w, h, g2)
    if tint is None or strength <= 0:
        return
    m = min(1.0, max(0.0, mode))
    big = max(w, h) * 0.55
    cx = _mix(LIBRARY_GLOW[0], PLAYER_GLOW[0], m) * w
    cy = _mix(LIBRARY_GLOW[1], PLAYER_GLOW[1], m) * h
    rx = _mix(LIBRARY_GLOW[2] * w, big, m)
    ry = _mix(LIBRARY_GLOW[3] * h, big, m)
    _glow(p, cx, cy, rx, ry, QColor(tint), _mix(LIBRARY_ALPHA, PLAYER_ALPHA, m) * strength, w, h)
    c2 = QColor.fromHsv((tint.hue() + 40) % 360, tint.saturation(), tint.value())
    r2 = _mix(LIBRARY_GLOW2[2], PLAYER_GLOW2[2], m) * max(w, h)
    _glow(p, _mix(LIBRARY_GLOW2[0], PLAYER_GLOW2[0], m) * w, _mix(LIBRARY_GLOW2[1], PLAYER_GLOW2[1], m) * h,
          r2, r2, c2, _mix(80, 90, m) * strength, w, h)