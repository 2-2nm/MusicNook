from PySide6.QtGui import QColor, QRadialGradient

from ui import theme


def paint_backdrop(p, w: int, h: int):
    p.fillRect(0, 0, w, h, QColor(theme.BG))
    g = QRadialGradient(w * 0.12, 0, w * 0.75)
    g.setColorAt(0, QColor(32, 52, 170, 230))
    g.setColorAt(1, QColor(32, 52, 170, 0))
    p.fillRect(0, 0, w, h, g)
    g2 = QRadialGradient(w, h, w * 0.55)
    g2.setColorAt(0, QColor(110, 40, 160, 150))
    g2.setColorAt(1, QColor(110, 40, 160, 0))
    p.fillRect(0, 0, w, h, g2)