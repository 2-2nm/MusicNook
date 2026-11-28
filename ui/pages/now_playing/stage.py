from math import atan2, degrees, hypot

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QConicalGradient, QImage, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import QSizePolicy, QWidget

from ui.rendering.cover_renderer import CoverRenderer
from ui import theme
from ui.rendering.accent import glow_hsv

COVER = 340
DISC_R = 150
STAGE_W = COVER + 150  # the record peeks out 150px to the right of the cover
STAGE_H = COVER
VINYL_C = QPointF(COVER, COVER / 2)
DISC_COLOR = QColor(11, 11, 16)
SPIN_DEG_PER_SEC = 60.0  # the record turns 2 degrees every 33 ms while playing; scrubbing uses the same ratio
COVER_RADIUS = 28
COVER_BORDER = 46     # alpha of the thin white line around the cover
MAX_SCALE = 1.8      # biggest size of the stage relative to the base size (reached in fullscreen)
GROW_FROM_H, GROW_TO_H = 820, 1200  # window heights: up to the first the stage keeps its base size, the second gives MAX_SCALE


def dominant_color(track) -> QColor:
    """Glow colour of a cover (see glow_hsv): vivid for a colourful cover, dark and muted for a mostly black one."""
    if track is None:
        return QColor(theme.ACCENT)
    img = CoverRenderer.pixmap(track, 48, 0).toImage().convertToFormat(QImage.Format_ARGB32)
    pixels = []
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.alpha() >= 128:
                pixels.append((c.hsvHue(), c.hsvSaturationF(), c.valueF()))
    picked = glow_hsv(pixels, QColor(theme.ACCENT).hsvHueF() * 360)
    if picked is None:  # nothing to look at (empty cover): the app's own accent
        return QColor(theme.ACCENT)
    h, sat, val = picked
    return QColor.fromHsvF(h / 360, sat, val)


class Stage(QWidget):
    """Big cover with a vinyl record behind it. The record spins while the music plays.

    Easter egg: grab the record and turn it. Clockwise winds the song forward, counter-clockwise rewinds it, at
    the speed the record turns while playing (60 degrees = 1 second), like a real record."""
    scrubStarted = Signal()
    scrubbed = Signal(float)   # seconds moved since the grab (negative = back)
    scrubFinished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._track = None
        self._angle = 0.0
        self._playing = False
        self._accent = QColor(theme.ACCENT)
        self._cover_ghost = False  # the cover is flying (ui/shell/cover_flight.py): leave it out
        self._intro = 1.0          # 0..1: glow and record appear (1 = fully there)
        self._grab_angle = None   # mouse angle (degrees, clockwise) at the last mouse event while the record is held
        self._grab_total = 0.0    # degrees turned since the grab
        self.setMouseTracking(True)
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

    def set_cover_ghost(self, ghost: bool):
        self._cover_ghost = ghost
        self.update()

    def set_intro(self, v: float):
        """Fades the glow and slides the record out from behind the cover (used while the cover lands)."""
        self._intro = min(1.0, max(0.0, v))
        self.update()

    def cover_rect(self) -> tuple[QRectF, float]:
        """Where the cover is drawn, in this widget's coordinates, and its corner radius."""
        s, top = self._geometry()
        return QRectF(0, top, COVER * s, COVER * s), COVER_RADIUS * s

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

    def _max_scale(self) -> float:
        """1.0 in a normal window (so it looks as before), growing smoothly to MAX_SCALE as the window gets taller."""
        t = (self.window().height() - GROW_FROM_H) / (GROW_TO_H - GROW_FROM_H)
        return 1.0 + (MAX_SCALE - 1.0) * min(1.0, max(0.0, t))

    def _geometry(self):
        """(scale, top of the cover): the cover is centred vertically in the stage."""
        s = min(self.width() / STAGE_W, self.height() / STAGE_H, self._max_scale())
        return s, (self.height() - STAGE_H * s) / 2

    # ---------- turning the record by hand ----------
    def _on_record(self, pos) -> bool:
        """True where the visible part of the record is (the cover is on top of the rest)."""
        if self._track is None or self._intro < 1.0:
            return False
        s, top = self._geometry()
        x, y = pos.x() / s, (pos.y() - top) / s
        if 0 <= x <= COVER and 0 <= y <= COVER:
            return False
        return hypot(x - VINYL_C.x(), y - VINYL_C.y()) <= DISC_R

    def _mouse_angle(self, pos) -> float:
        s, top = self._geometry()
        return degrees(atan2(pos.y() - top - VINYL_C.y() * s, pos.x() - VINYL_C.x() * s))  # clockwise on screen

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._on_record(e.position()):
            self._grab_angle = self._mouse_angle(e.position())
            self._grab_total = 0.0
            self.setCursor(Qt.PointingHandCursor)
            self.scrubStarted.emit()
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._grab_angle is None:
            self.setCursor(Qt.PointingHandCursor if self._on_record(e.position()) else Qt.ArrowCursor)
            return
        a = self._mouse_angle(e.position())
        step = (a - self._grab_angle + 180) % 360 - 180  # shortest way round, so crossing 180 degrees is smooth
        self._grab_angle = a
        self._grab_total += step
        self._angle = (self._angle - step) % 360  # the record follows the mouse
        self.scrubbed.emit(self._grab_total / SPIN_DEG_PER_SEC)
        self.update()

    def mouseReleaseEvent(self, e):
        if self._grab_angle is not None and e.button() == Qt.LeftButton:
            self._grab_angle = None
            self.setCursor(Qt.PointingHandCursor if self._on_record(e.position()) else Qt.ArrowCursor)
            self.scrubFinished.emit()
        else:
            super().mouseReleaseEvent(e)

    def _tick(self):
        if self._grab_angle is None:  # held by the user: it only moves with the mouse
            self._angle = (self._angle - 2.0) % 360  # clockwise, like a real record
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        s, top = self._geometry()
        p.translate(0, top)  # left aligned with the title below
        p.scale(s, s)
        p.setPen(Qt.NoPen)

        intro = self._intro
        p.setOpacity(intro)
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
        p.translate(-(1.0 - intro) * 70, 0)  # comes out from behind the cover
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
        p.translate((1.0 - intro) * 70, 0)
        p.setOpacity(1.0)
        if self._cover_ghost:
            return

        # cover on top
        # rendered at the size it is shown (in steps of 32 px, so resizing does not fill the cache), not scaled up
        size = -(-int(COVER * s) // 32) * 32
        radius = round(COVER_RADIUS * size / COVER)
        px = CoverRenderer.pixmap(self._track, size, radius) if self._track else CoverRenderer.placeholder(size, radius)
        p.drawPixmap(QRectF(0, 0, COVER, COVER), px, QRectF(px.rect()))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, COVER_BORDER), 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, COVER - 1, COVER - 1), COVER_RADIUS, COVER_RADIUS)