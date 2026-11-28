from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ui import theme
from ui.components.smooth_scroll import SmoothScrollArea
from ui.components.song_list import FADE_H, FadeOverlay
from ui.pages.library.albums.grid import AlbumGrid
from ui.pages.library.artists.albums_row import ArtistAlbumTile
from ui.pages.library.artists.hero import ArtistHero
from ui.pages.library.artists.list import ArtistList
from ui.pages.library.artists.popular import PopularList
from ui.pages.library.artists.transition import Crossfade

LIST_W = 400
ALBUMS_W = 400
POPULAR_N = 6


def _heading(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setFont(theme.font(24, QFont.Weight.Bold))
    lb.setStyleSheet(f"color:{theme.TEXT};")
    return lb


class ArtistsView(QWidget):
    """Artists tab: every artist A-Z on the left; the selected artist (hero, popular songs, albums) on the right."""
    playRequested = Signal(list, int)   # tracks, start index
    shuffleRequested = Signal(list)
    queueRequested = Signal(list)
    albumRequested = Signal(str)        # album key: the window opens it in the Albums tab

    def __init__(self, parent=None):
        super().__init__(parent)
        self._artists: list = []
        self._stats: dict = {}
        self._query = ""
        self._selected = None  # artist key
        self._sig = None
        self._popular: list = []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(28)

        self.list = ArtistList()
        self.list.setFixedWidth(LIST_W)
        self.list.selected.connect(self._select)
        lay.addWidget(self.list)

        self.scroll = SmoothScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        body = QWidget()
        bl = QVBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(28)
        self.hero = ArtistHero()
        self.hero.playClicked.connect(lambda: self._play_all(False))
        self.hero.shuffleClicked.connect(lambda: self._emit_all(self.shuffleRequested))
        self.hero.queueClicked.connect(lambda: self._emit_all(self.queueRequested))
        bl.addWidget(self.hero)

        cols = QHBoxLayout()
        cols.setSpacing(36)
        pop = QVBoxLayout()
        pop.setSpacing(12)
        pop.addWidget(_heading("Popular songs"))
        self.pop = PopularList()
        self.pop.rowClicked.connect(self._play_popular)
        pop.addWidget(self.pop)
        pop.addStretch(1)
        cols.addLayout(pop, 1)
        alb_w = QWidget()
        alb_w.setFixedWidth(ALBUMS_W)
        alb = QVBoxLayout(alb_w)
        alb.setContentsMargins(0, 0, 0, 0)
        alb.setSpacing(12)
        alb.addWidget(_heading("Albums"))
        self.grid = AlbumGrid()
        alb.addWidget(self.grid)
        alb.addStretch(1)
        cols.addWidget(alb_w, 0, Qt.AlignTop)
        bl.addLayout(cols)
        bl.addStretch(1)
        self.scroll.setWidget(body)
        body.setAutoFillBackground(False)
        self.scroll.viewport().setAutoFillBackground(False)
        lay.addWidget(self.scroll, 1)
        self._fade_pane = Crossfade(self.scroll, body)  # picking another artist cross-fades the right side

        self.empty = QLabel("No artists found.", self.list)
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
        self.empty.setGeometry(0, 70, self.list.width(), 30)

    # ---------- data ----------
    def set_artists(self, artists: list, stats: dict):
        self._stats = stats
        if artists != self._artists or not self.list.rows():
            self._artists = artists
            self._rebuild()
        else:
            self._apply_selection()  # only the play counts may have changed

    def set_query(self, q: str):
        q = q.strip().casefold()
        if q != self._query:
            self._query = q
            self._rebuild()

    def set_current(self, track_id):
        self.pop.set_current(track_id)

    def shown(self) -> list:
        q = self._query
        return [a for a in self._artists if not q or q in a.name.casefold()]

    def _rebuild(self):
        shown = self.shown()
        keys = {a.key for a in shown}
        if self._selected not in keys:
            self._selected = shown[0].key if shown else None
        self.list.set_artists(shown, self._selected)
        self._apply_selection()
        self.empty.setVisible(not shown)

    def _select(self, artist):
        if artist.key == self._selected:
            return
        self._selected = artist.key
        self.list.set_selected(artist.key, True)  # the highlight glides to the new row
        self._fade_pane.run(self._change_artist)

    def _change_artist(self):
        self.scroll.verticalScrollBar().setValue(0)  # the new artist starts at the top
        self._apply_selection()

    def _apply_selection(self):
        chosen = next((a for a in self._artists if a.key == self._selected), None)
        popular = chosen.popular(self._stats, POPULAR_N) if chosen else []
        sig = (chosen, tuple(t.id for t in popular))
        if sig == self._sig:
            return
        if chosen != self.hero.artist:
            self.hero.set_artist(chosen)
            tiles = []
            for a in (chosen.albums if chosen else ()):
                t = ArtistAlbumTile(a)
                t.clicked.connect(lambda alb: self.albumRequested.emit(alb.key))
                tiles.append(t)
            self.grid.set_tiles(tiles)
        self._popular = popular
        self.pop.set_tracks(popular)
        self._sig = sig

    # ---------- actions ----------
    def _play_all(self, _=False):
        if self.hero.artist:
            self.playRequested.emit(list(self.hero.artist.tracks), 0)

    def _play_popular(self, index: int):
        if self._popular:
            self.playRequested.emit(list(self._popular), index)

    def _emit_all(self, signal):
        if self.hero.artist:
            signal.emit(list(self.hero.artist.tracks))