from PySide6.QtWidgets import QVBoxLayout, QWidget

from ui.components.fade_stack import FadeStack
from ui.pages.library.albums import AlbumsView
from ui.pages.library.songs_view import SongsView

TAB_SONGS, TAB_ALBUMS = 0, 1  # same order as the header tabs (Artists / Folders still show the song list)


class LibraryPage(QWidget):
    """Library: a stack with the Songs view and the Albums view, switched by the header tabs."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.songs_view = SongsView(model)
        self.albums = AlbumsView()
        # kept so the window can keep talking to the song widgets directly
        self.card, self.recent, self.songs = self.songs_view.card, self.songs_view.recent, self.songs_view.songs
        self.stack = FadeStack(duration=200)
        self.stack.addWidget(self.songs_view)
        self.stack.addWidget(self.albums)
        lay.addWidget(self.stack, 1)

    def set_tab(self, tab: int):
        self.stack.fade_to(1 if tab == TAB_ALBUMS else 0)
