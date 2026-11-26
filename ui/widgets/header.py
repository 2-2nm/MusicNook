import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ui import theme
from ui.widgets.window_controls import WindowControls

PILL_H = 42  # shared height of the tab pill, the search box and the caption pill


class LibraryHeader(QWidget):
    searchChanged = Signal(str)
    tabChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        left = QVBoxLayout()
        left.setSpacing(0)
        title = QLabel("Library")
        title.setFont(theme.font(34, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{theme.TEXT};")
        self.subtitle = QLabel("0 songs")
        self.subtitle.setFont(theme.font(15))
        self.subtitle.setStyleSheet(f"color:{theme.MUTED};")
        left.addWidget(title)
        left.addWidget(self.subtitle)
        lay.addLayout(left)
        lay.addStretch(1)

        seg = QFrame()
        seg.setObjectName("segFrame")
        seg.setFixedHeight(PILL_H)
        sl = QHBoxLayout(seg)
        sl.setContentsMargins(4, 4, 4, 4)
        sl.setSpacing(2)
        self._group = QButtonGroup(self)
        for i, name in enumerate(("Songs", "Albums", "Artists", "Folders")):
            b = QPushButton(name)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setFixedHeight(PILL_H - 8)
            b.setCursor(Qt.PointingHandCursor)
            self._group.addButton(b, i)
            sl.addWidget(b)
        self._group.button(0).setChecked(True)
        self._group.idClicked.connect(self.tabChanged)
        # Every pill is top-aligned and PILL_H tall, so they all share one center line
        lay.addWidget(seg, 0, Qt.AlignTop)
        lay.addStretch(1)

        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Search songs, albums, artists")
        self.search.setFixedSize(300, PILL_H)
        self.search.textChanged.connect(self.searchChanged)
        lay.addWidget(self.search, 0, Qt.AlignTop)
        lay.addSpacing(12)

        self.controls = WindowControls()
        self.controls.setFixedHeight(PILL_H)
        lay.addWidget(self.controls, 0, Qt.AlignTop)

    def set_stats(self, count: int, total_seconds: float):
        h, m = int(total_seconds // 3600), int(total_seconds % 3600 // 60)
        self.subtitle.setText(f"{count} songs · {h} h {m} m")

    # Non-Windows fallback only: on Windows dragging and double-click are handled natively (HTCAPTION)
    def mousePressEvent(self, e):
        if sys.platform != "win32" and e.button() == Qt.LeftButton:
            handle = self.window().windowHandle()
            if handle:
                handle.startSystemMove()
                return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if sys.platform != "win32":
            w = self.window()
            w.showNormal() if w.isMaximized() else w.showMaximized()
            return
        super().mouseDoubleClickEvent(e)