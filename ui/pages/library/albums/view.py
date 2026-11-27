from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QWidget

from ui import theme
from ui.components.smooth_scroll import SmoothScrollArea
from ui.components.song_list import FADE_H, FadeOverlay
from ui.pages.library.albums.detail import AlbumDetail
from ui.pages.library.albums.grid import AlbumGrid, AlbumTile

DETAIL_W = 430


class AlbumsView(QWidget):
    """Albums tab: the album grid on the left, the selected album on the right."""
    playRequested = Signal(list, int)   # tracks, start index
    shuffleRequested = Signal(list)
    queueRequested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._albums: list = []
        self._query = ""
        self._selected = None  # album key
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(28)

        self.scroll = SmoothScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.grid = AlbumGrid()
        self.scroll.setWidget(self.grid)
        self.grid.setAutoFillBackground(False)  # setWidget() switches it on (white block)
        self.scroll.viewport().setAutoFillBackground(False)
        lay.addWidget(self.scroll, 1)

        self.detail = AlbumDetail()
        self.detail.setFixedWidth(DETAIL_W)
        self.detail.playRequested.connect(self._play)
        self.detail.shuffleClicked.connect(lambda: self._emit_album(self.shuffleRequested))
        self.detail.queueClicked.connect(lambda: self._emit_album(self.queueRequested))
        lay.addWidget(self.detail)

        self.empty = QLabel("No albums found.", self.scroll)
        self.empty.setFont(theme.font(16))
        self.empty.setStyleSheet(f"color:{theme.MUTED};")
        self.empty.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.empty.hide()
        self.fade = FadeOverlay(self)
        self.fade.raise_()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        v = self.scroll.geometry()
        self.fade.setGeometry(v.x(), v.bottom() - FADE_H + 1, v.width(), FADE_H)
        self.fade.raise_()
        self.empty.setGeometry(0, 60, self.scroll.width(), 30)

    # ---------- data ----------
    def set_albums(self, albums: list):
        self._albums = albums
        self._rebuild()

    def set_query(self, q: str):
        q = q.strip().casefold()
        if q != self._query:
            self._query = q
            self._rebuild()

    def set_current(self, track_id):
        self.detail.set_current(track_id)

    def shown(self) -> list:
        q = self._query
        return [a for a in self._albums if not q or q in a.title.casefold() or q in a.artist.casefold()]

    def _rebuild(self):
        shown = self.shown()
        tiles = []
        for a in shown:
            t = AlbumTile(a)
            t.clicked.connect(self._select)
            tiles.append(t)
        self.grid.set_tiles(tiles)
        keys = {a.key for a in shown}
        if self._selected not in keys:
            self._selected = shown[0].key if shown else None
        self._apply_selection()
        self.empty.setVisible(not shown)

    def _select(self, album):
        self._selected = album.key
        self._apply_selection()

    def _apply_selection(self):
        chosen = None
        for t in self.grid.tiles():
            on = t.album.key == self._selected
            t.set_selected(on)
            if on:
                chosen = t.album
        if chosen != self.detail.album:  # value comparison: also true when the album's songs changed
            self.detail.set_album(chosen)

    # ---------- actions ----------
    def _play(self, index: int):
        if self.detail.album:
            self.playRequested.emit(list(self.detail.album.tracks), index)

    def _emit_album(self, signal):
        if self.detail.album:
            signal.emit(list(self.detail.album.tracks))
