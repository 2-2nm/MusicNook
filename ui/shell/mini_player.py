from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui import theme
from ui.icons import draw_icon
from ui.components.common import Card, CoverLabel, ElidedLabel, IconButton, PlayButton
from ui.pages.now_playing.waveform import WaveformSeek
from ui.components.progress_bar import ProgressBar


class VolumeIcon(QWidget):
    """Speaker icon that tells what the white slider next to it is for; it shows the level (muted / low / high)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self._name = "volume"

    def set_level(self, v: float):
        name = "volume_mute" if v <= 0.001 else "volume_low" if v < 0.5 else "volume"
        if name != self._name:
            self._name = name
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        draw_icon(p, self._name, QRectF(self.rect()), theme.MUTED)


class MiniPlayer(Card):
    prevClicked = Signal()
    nextClicked = Signal()
    toggleClicked = Signal()
    seekRequested = Signal(float)
    volumeChanged = Signal(float)
    openRequested = Signal()  # a click on the player itself (not on one of its controls)
    radius = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(76)
        self.setCursor(Qt.PointingHandCursor)
        self._pressed = False
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 24, 0)
        lay.setSpacing(14)
        self.cover = CoverLabel(48, 12)
        lay.addWidget(self.cover)

        info = QVBoxLayout()
        info.setSpacing(0)
        info.addStretch(1)
        self.title = ElidedLabel("Not playing", 16, QFont.Weight.DemiBold)
        self.artist = ElidedLabel("", 14, color=theme.MUTED)
        info.addWidget(self.title)
        info.addWidget(self.artist)
        info.addStretch(1)
        wrap = QHBoxLayout()
        wrap.addLayout(info)
        lay.addLayout(wrap, 2)

        prev = IconButton("prev", 40, 22)
        nxt = IconButton("next", 40, 22)
        self.play_btn = PlayButton(52)
        prev.clicked.connect(self.prevClicked)
        nxt.clicked.connect(self.nextClicked)
        self.play_btn.clicked.connect(self.toggleClicked)
        lay.addWidget(prev)
        lay.addWidget(self.play_btn)
        lay.addWidget(nxt)

        self.t_cur, self.t_tot = QLabel("0:00"), QLabel("0:00")
        for l in (self.t_cur, self.t_tot):
            l.setFont(theme.font(14))
            l.setStyleSheet(f"color:{theme.MUTED};")
        self.bar = WaveformSeek(36)  # same waveform as the Now playing page
        self.bar.seekRequested.connect(self.seekRequested)
        lay.addWidget(self.t_cur)
        lay.addWidget(self.bar, 5)
        lay.addWidget(self.t_tot)

        self.vol_icon = VolumeIcon()
        self.volume = ProgressBar("#ffffff", "#ffffff")
        self.volume.setFixedWidth(100)
        self.volume.seekRequested.connect(self.volumeChanged)
        vol = QHBoxLayout()
        vol.setSpacing(8)
        vol.addWidget(self.vol_icon)
        vol.addWidget(self.volume)
        lay.addLayout(vol)

    # Buttons, the waveform and the volume slider take their own clicks; labels and the cover ignore the mouse,
    # so a click on those (or on the empty parts of the card) arrives here and opens the Now playing page.
    def mousePressEvent(self, e):
        self._pressed = e.button() == Qt.LeftButton
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        if self._pressed and e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.openRequested.emit()
        self._pressed = False
        super().mouseReleaseEvent(e)

    def paint_background(self, p: QPainter, r: QRectF):
        p.setBrush(QColor(14, 16, 28, 235))
        p.setPen(QColor(255, 255, 255, 30))
        p.drawRoundedRect(r, self.radius, self.radius)

    def set_track(self, track):
        self.cover.set_track(track)
        self.bar.set_track(track)
        self.title.setText(track.title)
        self.artist.setText(track.artist)

    def set_playing(self, v: bool):
        self.play_btn.set_playing(v)

    def set_progress(self, pos_ms: int, dur_ms: int):
        self.t_cur.setText(theme.fmt_time(pos_ms))
        self.t_tot.setText(theme.fmt_time(dur_ms))
        self.bar.set_value(pos_ms / dur_ms if dur_ms else 0)

    def set_volume(self, v: float):
        self.volume.set_value(v)
        self.vol_icon.set_level(v)