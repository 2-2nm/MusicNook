from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from models.track_list_model import TrackListModel
from ui import theme
from ui.widgets.header import CapsuleButton
from ui.widgets.song_list import SORTS, SongList


class CollectionPage(QWidget):
    """The songs of one playlist or smart collection (title and stats live in the window header)."""
    backClicked = Signal()
    playClicked = Signal()
    shuffleClicked = Signal()
    rowActivated = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.back = CapsuleButton("\u2190  Playlists", "secondary")
        self.shuffle_btn = CapsuleButton("Shuffle", "secondary")
        self.play_btn = CapsuleButton("Play", "primary")
        self.back.clicked.connect(lambda: self.backClicked.emit())
        self.shuffle_btn.clicked.connect(lambda: self.shuffleClicked.emit())
        self.play_btn.clicked.connect(lambda: self.playClicked.emit())
        top.addWidget(self.back)
        top.addStretch(1)
        top.addWidget(self.shuffle_btn)
        top.addWidget(self.play_btn)
        lay.addLayout(top)
        lay.addSpacing(16)

        self.desc = QLabel("")
        self.desc.setWordWrap(True)
        self.desc.setFont(theme.font(15))
        self.desc.setStyleSheet(f"color:{theme.MUTED};")
        self.desc.setContentsMargins(0, 0, 0, 14)
        self.desc.hide()
        lay.addWidget(self.desc)

        self.model = TrackListModel(self)
        self.songs = SongList(self.model, sorts={"manual": "Default order", **SORTS}, heading="Songs")
        self.songs.rowActivated.connect(self.rowActivated)
        lay.addWidget(self.songs, 1)

        self.empty = QLabel("")
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.empty.setFont(theme.font(16))
        self.empty.setStyleSheet(f"color:{theme.MUTED};")
        self.empty.setContentsMargins(0, 60, 0, 0)
        self.empty.hide()
        # Only one of the two is visible at a time, and hidden widgets take no space, so the visible one gets
        # all of it. (A trailing stretch here used to split the height in half with the song list.)
        lay.addWidget(self.empty, 1)

    def set_description(self, text: str):
        self.desc.setText(text)
        self.desc.setVisible(bool(text.strip()))

    def set_tracks(self, tracks: list, empty_text: str, reset: bool = True):
        """reset=False keeps the sort / filter the user chose (used when the data changes under an open page)."""
        if reset:
            self.songs.reset("manual")
        self.model.set_tracks(tracks)
        has = bool(tracks) or bool(self.model.formats)
        self.songs.setVisible(has)
        self.empty.setVisible(not has)
        self.empty.setText(empty_text)
        self.play_btn.setEnabled(bool(tracks))
        self.shuffle_btn.setEnabled(bool(tracks))