import os

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from domain.folder import Folder, count_under
from ui import theme
from ui.components.common import ElidedLabel
from ui.components.song_list import FADE_H, FadeOverlay
from ui.icons import draw_icon
from ui.shell.header import CapsuleButton, theme_text_width

WARN = "#ff9aa6"


class _RowButton(QAbstractButton):
    """Small pill button at the end of a folder row."""

    def __init__(self, text: str, danger: bool = False, parent=None):
        super().__init__(parent)
        self.setText(text)
        self._danger = danger
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)
        self.setFixedSize(theme_text_width(text) + 30, 34)

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            p.setOpacity(1.0 if self.isEnabled() else 0.4)
            hover = self.underMouse() and self.isEnabled()
            if self._danger:
                bg, fg = QColor(255, 84, 104, 70 if hover else 40), QColor(WARN)
            else:
                bg, fg = QColor(255, 255, 255, 51 if hover else 31), QColor(theme.TEXT)
            r = QRectF(self.rect())
            p.setPen(Qt.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
            p.setPen(fg)
            p.setFont(theme.font(14, QFont.Weight.DemiBold))
            p.drawText(r, Qt.AlignCenter, self.text())
        finally:
            p.end()


class FolderRow(QWidget):
    rescanClicked = Signal()
    removeClicked = Signal()
    H = 68

    def __init__(self, folder: Folder, status: str, warn: bool, busy: bool, parent=None):
        super().__init__(parent)
        self._warn = warn
        self.setFixedHeight(self.H)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(66, 0, 16, 0)
        lay.setSpacing(10)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addStretch(1)
        col.addWidget(ElidedLabel(folder.path, 15, QFont.Weight.DemiBold))
        col.addWidget(ElidedLabel(status, 13, color=WARN if warn else theme.MUTED))
        col.addStretch(1)
        lay.addLayout(col, 1)
        rescan = _RowButton("Rescan")
        rescan.setEnabled(not busy)
        rescan.clicked.connect(self.rescanClicked)
        remove = _RowButton("Remove", danger=True)
        remove.clicked.connect(self.removeClicked)
        lay.addWidget(rescan, 0, Qt.AlignVCenter)
        lay.addWidget(remove, 0, Qt.AlignVCenter)

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QColor(255, 255, 255, 12))
            p.setPen(QColor(255, 255, 255, 26))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 16, 16)
            draw_icon(p, "folder", QRectF(20, (self.height() - 26) / 2, 26, 26), WARN if self._warn else theme.MUTED)
        finally:
            p.end()


class _Empty(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        self.setFixedHeight(74)

    def paintEvent(self, e):
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            p.setBrush(QColor(0, 0, 0, 60))
            p.setPen(QPen(QColor(255, 255, 255, 80), 1.4, Qt.DashLine))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 16, 16)
            p.setPen(QColor(theme.MUTED))
            p.setFont(theme.font(14))
            p.drawText(QRectF(self.rect()), Qt.AlignCenter, self._text)
        finally:
            p.end()


class _Section(QWidget):
    addClicked = Signal()

    def __init__(self, title: str, blurb: str, empty_text: str, parent=None):
        super().__init__(parent)
        self._empty_text = empty_text
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        head = QHBoxLayout()
        head.setSpacing(16)
        col = QVBoxLayout()
        col.setSpacing(0)
        t = QLabel(title)
        t.setFont(theme.font(22, QFont.Weight.Bold))
        t.setStyleSheet(f"color:{theme.TEXT};")
        b = QLabel(blurb)
        b.setWordWrap(True)
        b.setFont(theme.font(14))
        b.setStyleSheet(f"color:{theme.MUTED};")
        col.addWidget(t)
        col.addWidget(b)
        head.addLayout(col, 1)
        add = CapsuleButton("+ Add folder", "secondary")
        add.clicked.connect(self.addClicked)
        head.addWidget(add, 0, Qt.AlignTop)
        lay.addLayout(head)
        lay.addSpacing(14)
        self._rows = QVBoxLayout()
        self._rows.setSpacing(10)
        lay.addLayout(self._rows)

    def set_rows(self, rows: list):
        while self._rows.count():
            w = self._rows.takeAt(0).widget()
            if w is not None:
                w.hide()
                w.deleteLater()  # not setParent(None): the click that triggered this rebuild is still running
        for w in rows or [_Empty(self._empty_text)]:
            self._rows.addWidget(w)


class FoldersPage(QWidget):
    """The folders of the app: music folders build the library, lyrics folders are searched for .lrc files."""
    addRequested = Signal(str)             # kind: "music" / "lyrics"
    rescanRequested = Signal(int, str)     # folder id, kind
    removeRequested = Signal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(34)
        self.music = _Section("Music folders", "The songs in these folders make up your library. "
                              "New files are picked up when you rescan.",
                              "No music folders yet. Add one to fill your library.")
        self.lyrics = _Section("Lyrics folders", "Synced .lrc files are looked up here when a song has "
                               "none next to it.", "No lyrics folders yet.")
        self.music.addClicked.connect(lambda: self.addRequested.emit("music"))
        self.lyrics.addClicked.connect(lambda: self.addRequested.emit("lyrics"))
        cl.addWidget(self.music)
        cl.addWidget(self.lyrics)
        cl.addStretch(1)
        cl.addSpacing(FADE_H)
        self.scroll.setWidget(content)
        # QScrollArea.setWidget() switches autoFillBackground on (a white block): off again after setWidget
        content.setAutoFillBackground(False)
        self.scroll.viewport().setAutoFillBackground(False)
        lay.addWidget(self.scroll, 1)
        self.fade = FadeOverlay(self)
        self.fade.raise_()
        self.set_data([], [], [], {}, False)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        v = self.scroll.geometry()
        self.fade.setGeometry(v.x(), v.bottom() - FADE_H + 1, v.width(), FADE_H)
        self.fade.raise_()

    def set_data(self, music: list, lyrics: list, tracks: list, lyric_counts: dict, scanning: bool):
        songs = count_under((t.path for t in tracks), [f.path for f in music])
        rows = []
        for f, n in zip(music, songs):
            warn = not os.path.isdir(f.path)
            status = ("Folder not found" if warn
                      else (f"Scanning...  {n:,} songs so far" if scanning else f"{n:,} song{'' if n == 1 else 's'}"))
            row = FolderRow(f, status, warn, scanning)
            row.rescanClicked.connect(lambda fid=f.id: self.rescanRequested.emit(fid, "music"))
            row.removeClicked.connect(lambda fid=f.id: self.removeRequested.emit(fid, "music"))
            rows.append(row)
        self.music.set_rows(rows)
        rows = []
        for f in lyrics:
            n = lyric_counts.get(f.id)
            warn = not os.path.isdir(f.path)
            status = ("Folder not found" if warn else "Reading..." if n is None
                      else f"{n:,} lyric file{'' if n == 1 else 's'}")
            row = FolderRow(f, status, warn, False)
            row.rescanClicked.connect(lambda fid=f.id: self.rescanRequested.emit(fid, "lyrics"))
            row.removeClicked.connect(lambda fid=f.id: self.removeRequested.emit(fid, "lyrics"))
            rows.append(row)
        self.lyrics.set_rows(rows)