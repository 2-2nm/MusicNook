from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui import theme
from ui.widgets.common import CoverLabel, ElidedLabel

COVER = 118


class RecentItem(QWidget):
    clicked = Signal(object)

    def __init__(self, track, parent=None):
        super().__init__(parent)
        self._track = track
        self.setFixedWidth(COVER)
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        c = CoverLabel(COVER, 18)
        c.set_track(track)
        lay.addWidget(c)
        lay.addSpacing(6)
        lay.addWidget(ElidedLabel(track.title, 15, QFont.Weight.DemiBold))
        lay.addWidget(ElidedLabel(track.artist, 13, color=theme.MUTED))

    def mousePressEvent(self, e):
        self.clicked.emit(self._track)


class RecentRow(QWidget):
    trackClicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        head = QLabel("RECENTLY ADDED")
        head.setFont(theme.font(12, QFont.Weight.Medium, 1.8))
        head.setStyleSheet(f"color:{theme.MUTED};")
        outer.addWidget(head)
        self._row = QHBoxLayout()
        self._row.setSpacing(16)
        self._row.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self._row)
        outer.addStretch(1)
        self.setFixedWidth(4 * COVER + 3 * 16)

    def set_tracks(self, tracks):
        while self._row.count():
            w = self._row.takeAt(0).widget()
            if w:
                w.deleteLater()
        for t in tracks[:4]:
            item = RecentItem(t)
            item.clicked.connect(self.trackClicked)
            self._row.addWidget(item)
        self._row.addStretch(1)
