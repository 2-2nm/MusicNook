from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ui import theme
from ui.widgets.common import Card, CoverLabel, ElidedLabel
from ui.widgets.progress_bar import ProgressBar


class ContinueCard(Card):
    resumeClicked = Signal()
    shuffleClicked = Signal()
    seekRequested = Signal(float)
    radius = 28

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(190)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 16, 22, 16)
        lay.setSpacing(20)
        self.cover = CoverLabel(158, 20)
        lay.addWidget(self.cover)

        col = QVBoxLayout()
        col.setSpacing(0)
        eyebrow = QLabel("CONTINUE LISTENING")
        eyebrow.setFont(theme.font(12, QFont.Weight.Medium, 1.8))
        eyebrow.setStyleSheet(f"color:{theme.MUTED};")
        self.title = ElidedLabel("Nothing playing yet", 30, QFont.Weight.Bold)
        self.sub = ElidedLabel("Add a music folder to get started", 16, color=theme.MUTED)
        col.addWidget(eyebrow)
        col.addSpacing(4)
        col.addWidget(self.title)
        col.addWidget(self.sub)
        col.addSpacing(8)

        prog = QHBoxLayout()
        prog.setSpacing(10)
        self.t_cur, self.t_tot = QLabel("0:00"), QLabel("0:00")
        for l in (self.t_cur, self.t_tot):
            l.setFont(theme.font(14))
            l.setStyleSheet(f"color:{theme.MUTED};")
        self.bar = ProgressBar()
        self.bar.seekRequested.connect(self.seekRequested)
        prog.addWidget(self.t_cur)
        prog.addWidget(self.bar, 1)
        prog.addWidget(self.t_tot)
        col.addLayout(prog)
        col.addStretch(1)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.resume_btn = QPushButton("Resume")  # reads "Pause" while a song is playing, see set_playing()
        self.resume_btn.setObjectName("primary")
        shuffle = QPushButton("Shuffle all")
        shuffle.setObjectName("secondary")
        for b in (self.resume_btn, shuffle):
            b.setFixedHeight(44)
            b.setCursor(Qt.PointingHandCursor)
        self.resume_btn.clicked.connect(self.resumeClicked)
        shuffle.clicked.connect(self.shuffleClicked)
        btns.addWidget(self.resume_btn)
        btns.addWidget(shuffle)
        btns.addStretch(1)
        col.addLayout(btns)
        lay.addLayout(col, 1)

    def paint_background(self, p: QPainter, r: QRectF):
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(38, 66, 190, 190))
        g.setColorAt(1, QColor(30, 14, 56, 235))
        p.setBrush(g)
        p.setPen(QColor(255, 255, 255, 40))
        p.drawRoundedRect(r, self.radius, self.radius)

    def set_track(self, track):
        self.cover.set_track(track)
        if track:
            self.title.setText(track.title)
            self.sub.setText(f"{track.artist} · {track.album}")

    def set_playing(self, playing: bool):
        self.resume_btn.setText("Pause" if playing else "Resume")

    def set_progress(self, pos_ms: int, dur_ms: int):
        self.t_cur.setText(theme.fmt_time(pos_ms))
        self.t_tot.setText(theme.fmt_time(dur_ms))
        self.bar.set_value(pos_ms / dur_ms if dur_ms else 0)