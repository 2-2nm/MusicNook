from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton

HOVER = QColor("#c42b1c")
ICON = QColor("#f2f2f2")


class CornerClose(QAbstractButton):
    """Close button whose hit area runs on to the window's top-right corner.

    The round button is drawn exactly over the slot in the caption pill, but the widget itself
    stretches up to the top edge and right to the window edge, so flinging the mouse into the
    corner still closes the window (like native Windows).
    """

    def __init__(self, parent, size: int = 34, glyph: int = 14):
        super().__init__(parent)
        self._size, self._glyph = size, glyph
        self._visual = QRectF(0, 0, size, size)
        self.setCursor(Qt.ArrowCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_Hover, True)

    def place(self, left: int, top: int, right_edge: int) -> None:
        """The round button is drawn with its top-left at (left, top); the widget itself
        reaches up to y=0 and across to `right_edge` (the window width)."""
        self._visual = QRectF(0, top, self._size, self._size)
        self.setGeometry(left, 0, max(self._size, right_edge - left), top + self._size)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Hover applies anywhere on the stretched hit area, not only over the circle
        if self.isDown() or self.underMouse():
            p.setPen(Qt.NoPen)
            p.setBrush(HOVER.darker(115) if self.isDown() else HOVER)
            p.drawEllipse(self._visual.adjusted(0.5, 0.5, -0.5, -0.5))
        pen = QPen(ICON, 1.6)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        c, d = self._visual.center(), self._glyph / 2 - 3
        P = QPointF
        p.drawLine(P(c.x() - d, c.y() - d), P(c.x() + d, c.y() + d))
        p.drawLine(P(c.x() + d, c.y() - d), P(c.x() - d, c.y() + d))
        p.end()