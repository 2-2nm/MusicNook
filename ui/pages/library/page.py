from PySide6.QtWidgets import QVBoxLayout, QWidget

from ui.components.fade_stack import FadeStack
from ui.pages.library.albums import AlbumsView
from ui.pages.library.artists import ArtistsView
from ui.pages.library.songs_view import SongsView

TAB_SONGS, TAB_ALBUMS, TAB_ARTISTS = 0, 1, 2  # same order as the header tabs


class LibraryPage(QWidget):
    """Library: a stack with the Songs, Albums and Artists views, switched by the header tabs."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.songs_view = SongsView(model)
        self.albums = AlbumsView()
        self.artists = ArtistsView()
        # kept so the window can keep talking to the song widgets directly
        self.card, self.recent, self.songs = self.songs_view.card, self.songs_view.recent, self.songs_view.songs
        self.stack = FadeStack(duration=200)
        self.stack.addWidget(self.songs_view)
        self.stack.addWidget(self.albums)
        self.stack.addWidget(self.artists)
        lay.addWidget(self.stack, 1)

    def set_tab(self, tab: int):
        self.stack.fade_to({TAB_ALBUMS: 1, TAB_ARTISTS: 2}.get(tab, 0))
