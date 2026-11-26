import string

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

from ui import theme

LETTERS = ["#"] + list(string.ascii_uppercase)


class AlphaIndex(QWidget):
    letterClicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(22)
        self.setMouseTracking(True)
        self._hover = -1

    def _idx(self, y: float) -> int:
        return min(len(LETTERS) - 1, max(0, int(y / (self.height() / len(LETTERS)))))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setFont(theme.font(11, QFont.Weight.DemiBold))
        step = self.height() / len(LETTERS)
        for i, l in enumerate(LETTERS):
            p.setPen(QColor(theme.ACCENT if i == self._hover else theme.DIM))
            p.drawText(QRectF(0, i * step, self.width(), step), Qt.AlignCenter, l)

    def mouseMoveEvent(self, e):
        i = self._idx(e.position().y())
        if i != self._hover:
            self._hover = i
            self.update()
        if e.buttons() & Qt.LeftButton:
            self.letterClicked.emit(LETTERS[i])

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.letterClicked.emit(LETTERS[self._idx(e.position().y())])

    def leaveEvent(self, e):
        self._hover = -1
        self.update()
