from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ui.components.song_list import SongList
from ui.pages.library.continue_card import ContinueCard
from ui.pages.library.recent_row import RecentRow


class SongsView(QWidget):
    """Songs tab: the Continue listening card, the newest albums and the song list."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        top = QHBoxLayout()
        top.setSpacing(36)
        self.card = ContinueCard()
        self.recent = RecentRow()
        top.addWidget(self.card, 1)
        top.addWidget(self.recent)
        lay.addLayout(top)
        lay.addSpacing(18)
        self.songs = SongList(model)
        lay.addWidget(self.songs, 1)
