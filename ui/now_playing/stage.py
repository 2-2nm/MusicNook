from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QConicalGradient, QImage, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QSizePolicy, QWidget

from services.cover_service import CoverService
from ui import theme

COVER = 340
DISC_R = 150
STAGE_W = COVER + 150  # the record peeks out 150px to the right of the cover
STAGE_H = COVER
VINYL_C = QPointF(COVER, COVER / 2)
DISC_COLOR = QColor(11, 11, 16)


HUE_BINS = 24


def pick_accent(pixels):
    """Accent colour the way Windows picks one from a wallpaper. `pixels` is an iterable of (h, s, v): hue 0-359,
    saturation and value 0-1. Dark, grey and washed-out pixels are ignored (a mostly black cover must not give
    a muddy brown), the rest vote for their hue, weighted by how vivid they are. The strongest hue wins and
    its pixels are averaged. Returns (h, s, v), or None when nothing on the cover is colourful."""
    weight = [0.0] * HUE_BINS
    hits = [[] for _ in range(HUE_BINS)]
    total = 0
    for h, sat, val in pixels:
        total += 1
        if h < 0 or sat < 0.28 or val < 0.22:
            continue
        w = sat * sat * val  # vivid and bright pixels count more
        i = int(h * HUE_BINS / 360) % HUE_BINS
        weight[i] += w
        hits[i].append((h, sat, val, w))
    if not total:
        return None
    # a hue's score includes its neighbours, so one colour split over two bins is not beaten by a single bin
    score = [weight[i] + 0.5 * (weight[i - 1] + weight[(i + 1) % HUE_BINS]) for i in range(HUE_BINS)]
    best = max(range(HUE_BINS), key=score.__getitem__)
    if weight[best] < 0.004 * total:  # almost no colour on the cover: grey / black / white artwork
        return None
    centre = (best + 0.5) * 360 / HUE_BINS
    sw = sh = ss = sv = 0.0
    for h, sat, val, w in hits[best]:
        sh += ((h - centre + 180) % 360 - 180) * w  # hue offset from the bin centre (handles the red wrap)
        ss += sat * w
        sv += val * w
        sw += w
    return ((centre + sh / sw) % 360, ss / sw, sv / sw)


def dominant_color(track) -> QColor:
    """Glow colour of a cover (see pick_accent), pushed towards a vivid tone so it works as a glow."""
    if track is None:
        return QColor(theme.ACCENT)
    img = CoverService.pixmap(track, 48, 0).toImage().convertToFormat(QImage.Format_ARGB32)
    pixels = []
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() >= 128:
                pixels.append((c.hsvHue(), c.hsvSaturationF(), c.valueF()))
    picked = pick_accent(pixels)
    if picked is None:  # grey / black cover: fall back to the app's own accent
        return QColor(theme.ACCENT)
    h, sat, val = picked
    return QColor.fromHsvF(h / 360, min(0.95, max(sat, 0.55)), min(0.95, max(val, 0.75)))


class Stage(QWidget):
    """Big cover with a vinyl record behind it. The record spins while the music plays."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._track = None
        self._angle = 0.0
        self._playing = False
        self._accent = QColor(theme.ACCENT)
        self._timer = QTimer(self, interval=33)
        self._timer.timeout.connect(self._tick)
        self.setMinimumSize(300, 220)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_track(self, track):
        self._track = track
        self.update()

    def set_accent(self, color: QColor):
        self._accent = QColor(color)
        self.update()

    def set_playing(self, playing: bool):
        self._playing = playing
        self._sync_timer()

    def _sync_timer(self):
        if self._playing and self.isVisible():
            self._timer.start()
        else:
            self._timer.stop()

    def showEvent(self, e):
        super().showEvent(e)
        self._sync_timer()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._sync_timer()

    def _tick(self):
        self._angle = (self._angle + 2.0) % 360
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        s = min(self.width() / STAGE_W, self.height() / STAGE_H, 1.0)
        p.translate(0, (self.height() - STAGE_H * s) / 2)  # left aligned with the title below
        p.scale(s, s)
        p.setPen(Qt.NoPen)

        # soft glow in the cover colour (kept inside the widget so it has no visible edge)
        a = QColor(self._accent)
        a.setAlpha(110)
        glow = QRadialGradient(QPointF(170, 172), 175)
        glow.setColorAt(0, a)
        a.setAlpha(0)
        glow.setColorAt(1, a)
        p.setBrush(glow)
        p.drawEllipse(QPointF(170, 172), 175, 175)

        # vinyl record
        p.setBrush(DISC_COLOR)
        p.drawEllipse(VINYL_C, DISC_R, DISC_R)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 10), 1))
        for r in range(60, DISC_R - 2, 4):
            p.drawEllipse(VINYL_C, r, r)
        sheen = QConicalGradient(VINYL_C, self._angle)
        for pos, alpha in ((0.0, 0), (0.04, 36), (0.10, 0), (0.50, 0), (0.54, 36), (0.60, 0), (1.0, 0)):
            sheen.setColorAt(pos, QColor(255, 255, 255, alpha))
        p.setPen(Qt.NoPen)
        p.setBrush(sheen)
        p.drawEllipse(VINYL_C, DISC_R, DISC_R)
        label = QLinearGradient(VINYL_C.x() - 48, VINYL_C.y() - 48, VINYL_C.x() + 48, VINYL_C.y() + 48)
        label.setColorAt(0, self._accent.lighter(125))
        label.setColorAt(1, self._accent.darker(160))
        p.setBrush(label)
        p.drawEllipse(VINYL_C, 48, 48)
        p.setBrush(DISC_COLOR)
        p.drawEllipse(VINYL_C, 7, 7)

        # cover on top
        px = CoverService.pixmap(self._track, COVER, 28) if self._track else CoverService.placeholder(COVER, 28)
        p.drawPixmap(0, 0, px)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 46), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, COVER - 1, COVER - 1), 28, 28)