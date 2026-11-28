import traceback

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen

from ui import theme
from ui.pages.library.albums.grid import RADIUS, AlbumTile
from ui.rendering.cover_renderer import CoverRenderer


class ArtistAlbumTile(AlbumTile):
    """Album tile of the Artists tab: title and year (the artist is already on screen)."""

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            self._paint(p)
        except Exception:
            traceback.print_exc()
        finally:
            p.end()

    def _paint(self, p: QPainter):
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        s = self.width()
        cover = QRectF(0, 0, s, s)
        p.drawPixmap(cover.toRect(), CoverRenderer.pixmap_async(self.album.tracks[0], s, RADIUS))
        if self._hover:
            clip = QPainterPath()
            clip.addRoundedRect(cover, RADIUS, RADIUS)
            p.fillPath(clip, QColor(0, 0, 0, 70))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 34)))
        p.drawRoundedRect(cover.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)
        p.setPen(QColor(theme.TEXT))
        p.setFont(theme.font(16, QFont.Weight.DemiBold))
        p.drawText(QRectF(2, s + 8, s - 4, 24), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(self.album.title, Qt.ElideRight, s - 4))
        p.setPen(QColor(theme.MUTED))
        p.setFont(theme.font(14))
        p.drawText(QRectF(2, s + 32, s - 4, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   str(self.album.year) if self.album.year else "")
