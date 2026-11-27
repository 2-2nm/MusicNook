from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QAbstractButton, QLabel, QSizePolicy, QWidget

from ui.rendering.cover_renderer import CoverRenderer
from ui import theme
from ui.icons import draw_icon


class Card(QWidget):
    """Rounded translucent panel. Override paint_background for custom fills."""
    radius = 22

    def paint_background(self, p: QPainter, r: QRectF):
        p.setBrush(QColor(255, 255, 255, 12))
        p.setPen(QColor(255, 255, 255, 26))
        p.drawRoundedRect(r, self.radius, self.radius)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        self.paint_background(p, QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))


class CoverLabel(QLabel):
    def __init__(self, size: int, radius: int, parent=None):
        super().__init__(parent)
        self._size, self._radius = size, radius
        self._ghost = False
        self.setFixedSize(size, size)
        self.set_track(None)

    @property
    def radius(self) -> int:
        return self._radius

    def set_ghost(self, ghost: bool):
        """Invisible (but still in the layout) while the cover is flying somewhere else, see ui/shell/cover_flight.py."""
        if ghost != self._ghost:
            self._ghost = ghost
            self.update()

    def paintEvent(self, e):
        if not self._ghost:
            super().paintEvent(e)

    def set_track(self, track):
        self.setPixmap(CoverRenderer.pixmap(track, self._size, self._radius) if track
                       else CoverRenderer.placeholder(self._size, self._radius))


class ElidedLabel(QLabel):
    def __init__(self, text="", px=14, weight=QFont.Weight.Normal, color=theme.TEXT, parent=None):
        super().__init__(parent)
        self._full = text
        self._color = QColor(color)
        self.setFont(theme.font(px, weight))
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setFixedHeight(int(px * 1.5))

    def setText(self, t: str):
        self._full = t
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setFont(self.font())
        p.setPen(self._color)
        p.drawText(self.rect(), Qt.AlignLeft | Qt.AlignVCenter,
                   self.fontMetrics().elidedText(self._full, Qt.ElideRight, self.width()))


class IconButton(QAbstractButton):
    def __init__(self, name: str, size=44, icon_px=22, checkable=False, parent=None):
        super().__init__(parent)
        self.name, self._icon_px = name, icon_px
        self.setFixedSize(size, size)
        self.setCheckable(checkable)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        active = self.isChecked() or self.underMouse()
        if self.isChecked():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 34))
            p.drawRoundedRect(QRectF(self.rect()), 14, 14)
        r = QRectF(0, 0, self._icon_px, self._icon_px)
        r.moveCenter(QRectF(self.rect()).center())
        draw_icon(p, self.name, r, "#ffffff" if active else theme.MUTED)


class PlayButton(QAbstractButton):
    def __init__(self, size=52, parent=None):
        super().__init__(parent)
        self._playing = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)

    def set_playing(self, v: bool):
        self._playing = v
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))
        r = QRectF(0, 0, 24, 24)
        r.moveCenter(QRectF(self.rect()).center())
        draw_icon(p, "pause" if self._playing else "play", r, "#0a0b14")
