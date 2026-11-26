from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QMenu, QScrollArea, QVBoxLayout, QHBoxLayout, QWidget

from models.playlist import Playlist
from ui import theme
from ui.icons import draw_icon
from ui.playlist.cover import custom_pixmap, draw_cover, mosaic_tracks
from ui.widgets.song_list import FADE_H, FadeOverlay

GAP = 22
MIN_TILE_W = 185
TEXT_H = 62
RADIUS = 20

# title, icon, gradient start, gradient end
SMART = [("Favourites", "heart", "#b0197c", "#6a22b5"),
         ("Recently played", "clock", "#1d4fd8", "#0f7a8f"),
         ("Most played", "trend", "#b84a0b", "#b91c24"),
         ("Recently added", "plus_circle", "#0e7a6d", "#1f4fd6")]


def _songs(n: int) -> str:
    return f"{n} song" if n == 1 else f"{n} songs"


class SmartCard(QWidget):
    clicked = Signal()

    def __init__(self, title: str, icon: str, c1: str, c2: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.title, self.icon, self.c1, self.c2, self.count = title, icon, c1, c2, 0
        self.setFixedHeight(94)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(self.c1))
        g.setColorAt(1, QColor(self.c2))
        p.setBrush(g)
        p.setPen(QColor(255, 255, 255, 46))
        p.drawRoundedRect(r, 20, 20)
        p.setPen(QColor("#ffffff"))
        p.setFont(theme.font(18, QFont.Weight.Bold))
        p.drawText(QRectF(22, 16, r.width() - 70, 26), Qt.AlignLeft | Qt.AlignVCenter, self.title)
        p.setPen(QColor(255, 255, 255, 215))
        p.setFont(theme.font(15))
        p.drawText(QRectF(22, 46, r.width() - 40, 24), Qt.AlignLeft | Qt.AlignVCenter, _songs(self.count))
        draw_icon(p, self.icon, QRectF(r.width() - 46, 16, 24, 24), "#ffffff")

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()


class NewTile(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.width()
        r = QRectF(1, 1, s - 2, s - 2)
        p.setBrush(QColor(0, 0, 0, 90))
        pen = QPen(QColor(255, 255, 255, 110), 1.6, Qt.DashLine)
        p.setPen(pen)
        p.drawRoundedRect(r, RADIUS, RADIUS)
        draw_icon(p, "plus", QRectF(s / 2 - 22, s / 2 - 36, 44, 44), "#ffffff")
        p.setPen(QColor(theme.TEXT))
        p.setFont(theme.font(16))
        p.drawText(QRectF(0, s / 2 + 14, s, 24), Qt.AlignHCenter | Qt.AlignVCenter, "New playlist")

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()


class PlaylistTile(QWidget):
    clicked = Signal(int)
    contextRequested = Signal(int, QPoint)  # the \u22ee button: where to pop the Play / Rename / Delete menu

    DOTS = 32  # diameter of the \u22ee button
    DOTS_MARGIN = 10

    def __init__(self, pl: Playlist, tracks: list, parent=None):
        super().__init__(parent)
        self.pl = pl
        self._covers = mosaic_tracks(tracks)
        self._custom = custom_pixmap(pl.cover)
        total = sum(t.duration for t in tracks)
        h, m = int(total // 3600), int(total % 3600 // 60)
        self._sub = _songs(len(tracks)) + (f" \u00b7 {h} h {m} m" if tracks else "")
        self._hover = False
        self._dots_hover = False
        self._menu_open = False
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)
        self.setMouseTracking(True)

    def _dots_rect(self) -> QRectF:
        s = self.width()
        return QRectF(s - self.DOTS_MARGIN - self.DOTS, self.DOTS_MARGIN, self.DOTS, self.DOTS)

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self._dots_hover = False
        self.update()

    def mouseMoveEvent(self, e):
        over = self._dots_rect().contains(e.position())
        if over != self._dots_hover:
            self._dots_hover = over
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        s = self.width()
        cover = QRectF(0, 0, s, s)
        clip = QPainterPath()
        clip.addRoundedRect(cover.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)
        p.save()
        p.setClipPath(clip)
        draw_cover(p, cover, self._covers, self._custom, self.devicePixelRatioF())
        active = self._hover or self._menu_open
        if active:
            p.fillRect(cover, QColor(0, 0, 0, 80))  # cover dims a little under the mouse
        p.restore()
        if active:
            d = self._dots_rect()
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 170 if (self._dots_hover or self._menu_open) else 120))
            p.drawEllipse(d)
            p.setBrush(QColor("#ffffff"))
            c = d.center()
            for dy in (-6, 0, 6):
                p.drawEllipse(QPointF(c.x(), c.y() + dy), 2.0, 2.0)
        p.setBrush(Qt.NoBrush)
        p.setPen(QColor(255, 255, 255, 34))
        p.drawPath(clip)
        p.setPen(QColor(theme.TEXT))
        p.setFont(theme.font(16, QFont.Weight.DemiBold))
        p.drawText(QRectF(0, s + 10, s, 24), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(self.pl.name, Qt.ElideRight, s))
        p.setPen(QColor(theme.MUTED))
        p.setFont(theme.font(14))
        p.drawText(QRectF(0, s + 34, s, 22), Qt.AlignLeft | Qt.AlignVCenter, self._sub)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self.rect().contains(e.position().toPoint()):
            return
        d = self._dots_rect()
        if d.contains(e.position()):
            self._menu_open = True
            self.update()
            try:
                self.contextRequested.emit(self.pl.id, self.mapToGlobal(QPoint(int(d.left()), int(d.bottom()) + 6)))
                self._menu_open = False
                self.update()
            except RuntimeError:
                pass  # the menu action rebuilt the grid and this tile is already gone
        else:
            self.clicked.emit(self.pl.id)


class PlaylistGrid(QWidget):
    """Tiles laid out in as many equal columns as fit; the height follows the number of rows."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tiles: list[QWidget] = []
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

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._layout()

    def _layout(self):
        w = self.width()
        if w <= 0 or not self._tiles:
            return
        cols = max(1, (w + GAP) // (MIN_TILE_W + GAP))
        tw = (w - GAP * (cols - 1)) // cols
        th = tw + TEXT_H
        for i, t in enumerate(self._tiles):
            r, c = divmod(i, cols)
            t.setGeometry(c * (tw + GAP), r * (th + GAP), tw, tw if isinstance(t, NewTile) else th)
        rows = -(-len(self._tiles) // cols)
        self.setMinimumHeight(rows * (th + GAP) - GAP + FADE_H)


class PlaylistsPage(QWidget):
    newRequested = Signal()
    playRequested = Signal(int)
    editRequested = Signal(int)
    deleteRequested = Signal(int)
    openRequested = Signal(int)  # a click on a playlist tile: show its songs
    smartRequested = Signal(int)  # 0 Favourites, 1 Recently played, 2 Most played, 3 Recently added

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list = []
        self._query = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        row = QHBoxLayout()
        row.setSpacing(20)
        self.cards = [SmartCard(*s) for s in SMART]
        for i, c in enumerate(self.cards):
            c.clicked.connect(lambda i=i: self.smartRequested.emit(i))
            row.addWidget(c, 1)
        lay.addLayout(row)
        lay.addSpacing(26)

        title = QLabel("Your playlists")
        title.setFont(theme.font(22, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{theme.TEXT};")
        lay.addWidget(title)
        lay.addSpacing(14)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.scroll.viewport().setAutoFillBackground(False)
        self.grid = PlaylistGrid()
        self.scroll.setWidget(self.grid)
        # QScrollArea.setWidget() switches autoFillBackground on for the content widget (that was the white
        # block), so it has to be switched off again after setWidget.
        self.grid.setAutoFillBackground(False)
        self.scroll.viewport().setAutoFillBackground(False)
        lay.addWidget(self.scroll, 1)

        self.fade = FadeOverlay(self)
        self.fade.raise_()
        self._rebuild()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        v = self.scroll.geometry()
        self.fade.setGeometry(v.x(), v.bottom() - FADE_H + 1, v.width(), FADE_H)
        self.fade.raise_()

    def set_data(self, items: list):
        """items: [(Playlist, [Track, ...]), ...]"""
        self._items = items
        self._rebuild()

    def set_smart_counts(self, counts: list[int]):
        for c, n in zip(self.cards, counts):
            c.count = n
            c.update()

    def set_query(self, q: str):
        self._query = q.strip().casefold()
        self._rebuild()

    def _rebuild(self):
        tiles = []
        if not self._query:
            nt = NewTile()
            nt.clicked.connect(self.newRequested)
            tiles.append(nt)
        for pl, tracks in self._items:
            if self._query and self._query not in pl.name.casefold():
                continue
            t = PlaylistTile(pl, tracks)
            t.clicked.connect(self.openRequested)
            t.contextRequested.connect(self._menu)
            tiles.append(t)
        self.grid.set_tiles(tiles)

    def _menu(self, pid: int, pos: QPoint):
        m = QMenu(self)
        m.addAction("Play", lambda checked=False: self.playRequested.emit(pid))
        m.addAction("Edit playlist", lambda checked=False: self.editRequested.emit(pid))
        m.addAction("Delete", lambda checked=False: self.deleteRequested.emit(pid))
        m.exec(pos)