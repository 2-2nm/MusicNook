from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ui import theme
from ui.widgets.common import Card, CoverLabel, ElidedLabel
from ui.now_playing.waveform import WaveformSeek


TIME_W = 44     # fixed width of the two time labels, so the waveform (and the buttons) line up
PROG_GAP = 10   # gap between a time label and the waveform
BTN_W = 112     # Pause and Resume are the same capsule
CARD_H = 208    # title + subtitle + waveform + buttons need ~175 px of inner height, so the waveform never touches the capsules


class ContinueCard(Card):
    resumeClicked = Signal()
    shuffleClicked = Signal()
    seekRequested = Signal(float)
    radius = 28

    def __init__(self, parent=None):
        super().__init__(parent)
        self._accent = None
        self.setFixedHeight(CARD_H)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 16, 22, 16)
        lay.setSpacing(20)
        self.cover = CoverLabel(CARD_H - 32, 22)  # fills the card's inner height
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
        prog.setSpacing(PROG_GAP)
        self.t_cur, self.t_tot = QLabel("0:00"), QLabel("0:00")
        for l, align in ((self.t_cur, Qt.AlignLeft), (self.t_tot, Qt.AlignRight)):
            l.setFont(theme.font(14))
            l.setStyleSheet(f"color:{theme.MUTED};")
            l.setFixedWidth(TIME_W)
            l.setAlignment(align | Qt.AlignVCenter)
        self.bar = WaveformSeek(34)  # same waveform as the Now playing page
        self.bar.seekRequested.connect(self.seekRequested)
        prog.addWidget(self.t_cur)
        prog.addWidget(self.bar, 1)
        prog.addWidget(self.t_tot)
        col.addLayout(prog)
        col.addSpacing(10)  # guaranteed gap between the waveform and the capsules
        col.addStretch(1)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        btns.setContentsMargins(TIME_W + PROG_GAP, 0, 0, 0)  # the buttons start where the waveform starts
        self.resume_btn = QPushButton("Resume")  # reads "Pause" while a song is playing, see set_playing()
        self.resume_btn.setObjectName("primary")
        shuffle = QPushButton("Shuffle")
        shuffle.setObjectName("secondary")
        for b in (self.resume_btn, shuffle):
            b.setFixedHeight(44)
            b.setCursor(Qt.PointingHandCursor)
        self.resume_btn.setFixedWidth(BTN_W)  # same width whether it reads Pause or Resume
        self.resume_btn.clicked.connect(self.resumeClicked)
        shuffle.clicked.connect(self.shuffleClicked)
        btns.addWidget(self.resume_btn)
        btns.addWidget(shuffle)
        btns.addStretch(1)
        col.addLayout(btns)
        lay.addLayout(col, 1)

    def set_accent(self, color):
        """Tint the card with the playing track's cover colour (None = the default blue-purple)."""
        self._accent = QColor(color) if color is not None else None
        self.update()

    def _gradient_colors(self):
        if self._accent is None:
            return QColor(38, 66, 190, 190), QColor(30, 14, 56, 235)
        h, s, v = self._accent.hsvHue(), self._accent.hsvSaturation(), self._accent.value()
        h = max(h, 0)
        start = QColor.fromHsv(h, min(255, int(s * 0.85)), int(v * 0.72))
        end = QColor.fromHsv((h + 35) % 360, min(255, int(s * 0.85)), int(v * 0.22))
        start.setAlpha(190)
        end.setAlpha(235)
        return start, end

    def paint_background(self, p: QPainter, r: QRectF):
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        c0, c1 = self._gradient_colors()
        g.setColorAt(0, c0)
        g.setColorAt(1, c1)
        p.setBrush(g)
        p.setPen(QColor(255, 255, 255, 40))
        p.drawRoundedRect(r, self.radius, self.radius)

    def set_track(self, track):
        self.cover.set_track(track)
        self.bar.set_track(track)
        if track:
            self.title.setText(track.title)
            self.sub.setText(f"{track.artist} · {track.album}")

    def set_playing(self, playing: bool):
        self.resume_btn.setText("Pause" if playing else "Resume")

    def set_progress(self, pos_ms: int, dur_ms: int):
        self.t_cur.setText(theme.fmt_time(pos_ms))
        self.t_tot.setText(theme.fmt_time(dur_ms))
        self.bar.set_value(pos_ms / dur_ms if dur_ms else 0)