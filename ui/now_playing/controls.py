from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QAbstractButton

from ui import theme
from ui.icons import draw_icon

# Icons drawn on a 24x24 grid (the shared icons.py has no shuffle / repeat yet)
_SHAPES = {
    "shuffle": [[(3, 7), (7, 7), (16, 17), (20, 17)], [(3, 17), (7, 17), (9.5, 14)], [(13, 10), (16, 7), (20, 7)],
                [(17.5, 4.5), (20.5, 7), (17.5, 9.5)], [(17.5, 14.5), (20.5, 17), (17.5, 19.5)]],
    "repeat": [[(4, 11), (4, 9), (6, 6.5), (19, 6.5)], [(16.5, 4), (19, 6.5), (16.5, 9)],
               [(20, 13), (20, 15), (18, 17.5), (5, 17.5)], [(7.5, 15), (5, 17.5), (7.5, 20)]],
}


class ModeButton(QAbstractButton):
    """Shuffle / repeat toggle. Active = accent colour with a small dot underneath."""

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self._on = False
        self._one = False
        self.setFixedSize(48, 48)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)

    def set_state(self, on: bool, one: bool = False):
        self._on, self._one = on, one
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = QColor(theme.ACCENT) if self._on else QColor("#ffffff" if self.underMouse() else theme.MUTED)
        p.save()
        p.translate(self.width() / 2 - 11, self.height() / 2 - 11)
        p.scale(22 / 24, 22 / 24)
        p.setPen(QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        for poly in _SHAPES[self.kind]:
            path = QPainterPath()
            path.moveTo(*poly[0])
            for pt in poly[1:]:
                path.lineTo(*pt)
            p.drawPath(path)
        if self._one:
            p.setFont(theme.font(10, QFont.Weight.Bold))
            p.drawText(QRectF(7, 7, 10, 10), Qt.AlignCenter, "1")
        p.restore()
        if self._on:
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawEllipse(QPointF(self.width() / 2, self.height() - 5), 2, 2)


class BigPlayButton(QAbstractButton):
    """White play / pause disc with a glow in the cover colour."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._playing = False
        self._accent = QColor(theme.ACCENT)
        self.setFixedSize(96, 96)
        self.setCursor(Qt.PointingHandCursor)

    def set_playing(self, v: bool):
        self._playing = v
        self.update()

    def set_accent(self, c: QColor):
        self._accent = QColor(c)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        a = QColor(self._accent)
        glow = QRadialGradient(c, 48)
        a.setAlpha(140)
        glow.setColorAt(0.0, a)
        a.setAlpha(80)
        glow.setColorAt(0.78, a)
        a.setAlpha(0)
        glow.setColorAt(1.0, a)
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(c, 48, 48)
        p.setBrush(QColor("#ffffff"))
        r = 36 if self.isDown() else 38
        p.drawEllipse(c, r, r)
        icon = QRectF(0, 0, 32, 32)
        icon.moveCenter(c)
        draw_icon(p, "pause" if self._playing else "play", icon, "#0a0b14")
