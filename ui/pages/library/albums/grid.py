from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from domain.album import Album
from ui import theme
from ui.components.song_list import FADE_H
from ui.rendering.cover_renderer import CoverRenderer

GAP = 22
MIN_TILE_W = 170
TEXT_H = 58
RADIUS = 20


class AlbumTile(QWidget):
    clicked = Signal(object)

    def __init__(self, album: Album, parent=None):
        super().__init__(parent)
        self.album = album
        self.selected = False
        self._hover = False
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)

    def set_selected(self, on: bool):
        if on != self.selected:
            self.selected = on
            self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        s = self.width()
        inset = 3 if self.selected else 0  # the ring sits outside the cover
        cover = QRectF(inset, inset, s - 2 * inset, s - 2 * inset)
        pm = CoverRenderer.pixmap(self.album.tracks[0], int(cover.width()), RADIUS)
        p.drawPixmap(cover.toRect(), pm)
        if self._hover and not self.selected:
            clip = QPainterPath()
            clip.addRoundedRect(cover, RADIUS, RADIUS)
            p.fillPath(clip, QColor(0, 0, 0, 70))
        p.setBrush(Qt.NoBrush)
        if self.selected:
            p.setPen(QPen(QColor(theme.ACCENT), 2.5))
            p.drawRoundedRect(QRectF(1.25, 1.25, s - 2.5, s - 2.5), RADIUS + 2, RADIUS + 2)
        else:
            p.setPen(QColor(255, 255, 255, 34))
            p.drawRoundedRect(cover.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)
        p.setPen(QColor(theme.TEXT))
        p.setFont(theme.font(16, QFont.Weight.DemiBold))
        p.drawText(QRectF(2, s + 8, s - 4, 24), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(self.album.title, Qt.ElideRight, s - 4))
        p.setPen(QColor(theme.MUTED))
        p.setFont(theme.font(14))
        p.drawText(QRectF(2, s + 32, s - 4, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(self.album.artist, Qt.ElideRight, s - 4))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.album)


class AlbumGrid(QWidget):
    """Tiles in as many equal columns as fit; the height follows the number of rows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tiles: list[AlbumTile] = []
        self.setAutoFillBackground(False)

    def set_tiles(self, tiles: list):
        for t in self._tiles:
            t.setParent(None)
            t.deleteLater()
        self._tiles = tiles
        for t in tiles:
            t.setParent(self)
            t.show()
        self._layout()

    def tiles(self) -> list:
        return self._tiles

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._layout()

    def _layout(self):
        w = self.width()
        if w <= 0 or not self._tiles:
            self.setMinimumHeight(0)
            return
        cols = max(1, (w + GAP) // (MIN_TILE_W + GAP))
        tw = (w - GAP * (cols - 1)) // cols
        th = tw + TEXT_H
        for i, t in enumerate(self._tiles):
            r, c = divmod(i, cols)
            t.setGeometry(c * (tw + GAP), r * (th + GAP), tw, th)
        rows = -(-len(self._tiles) // cols)
        self.setMinimumHeight(rows * (th + GAP) - GAP + FADE_H)
