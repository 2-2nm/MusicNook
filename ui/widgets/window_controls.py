from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QWidget

from ui.widgets.common import Card


class ControlButton(QAbstractButton):
    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(40, 34)
        self.setCursor(Qt.ArrowCursor)
        self.setAttribute(Qt.WA_Hover)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.underMouse():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 30))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(2, 0, -2, 0), 15, 15)
        pen = QPen(QColor("#f2f2f2"), 1.5)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        cx, cy = self.width() / 2, self.height() / 2
        P = QPointF
        if self.kind == "min":
            p.drawLine(P(cx - 5, cy), P(cx + 5, cy))
        elif self.kind == "max":
            p.drawRoundedRect(QRectF(cx - 5, cy - 5, 10, 10), 1.8, 1.8)
        elif self.kind == "restore":
            p.drawRoundedRect(QRectF(cx - 5.5, cy - 2.5, 8, 8), 1.6, 1.6)
            p.drawPolyline([P(cx - 2.5, cy - 2.5), P(cx - 2.5, cy - 5.5), P(cx + 5.5, cy - 5.5),
                            P(cx + 5.5, cy + 2.5), P(cx + 2.5, cy + 2.5)])


class WindowControls(Card):
    """Pill with minimize / maximize. The close button is a CornerClose floating above
    `close_slot`, so its hit area can reach the window corner."""
    radius = 21

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(42)
        self.setProperty("dragRegion", True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(0)
        self.btn_min = ControlButton("min")
        self.btn_max = ControlButton("max")
        self.close_slot = QWidget()  # placeholder for the real close button
        self.close_slot.setFixedSize(34, 34)
        for w in (self.btn_min, self.btn_max, self.close_slot):
            lay.addWidget(w)
        self.btn_min.clicked.connect(lambda: self.window().showMinimized())
        self.btn_max.clicked.connect(self._toggle_max)

    def _toggle_max(self):
        w = self.window()
        w.showNormal() if w.isMaximized() else w.showMaximized()

    def set_maximized(self, maximized: bool):
        self.btn_max.kind = "restore" if maximized else "max"
        self.btn_max.update()