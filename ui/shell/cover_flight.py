from math import ceil, pi, sin

from PySide6.QtCore import QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ui.rendering.cover_renderer import CoverRenderer

DURATION = 480  # ms


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


class CoverFlight(QWidget):
    """Shared-element transition: the cover of the playing song glides (and changes its corner radius) from one
    place in the window to another, e.g. from the Continue listening card to the big cover on the Player page.

    It is a transparent overlay over the whole window. The two real covers are hidden ("ghosted") while it
    runs, so there is only ever one cover on screen. `progressChanged` (0..1, already eased) lets the caller
    animate other things in step, e.g. fade the mini player in."""
    progressChanged = Signal(float)

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._anim = QVariantAnimation(self, duration=DURATION)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.valueChanged.connect(self._step)
        self._anim.finished.connect(self.finish)
        self._t = 0.0
        self._px = None
        self._on_done = None
        self._fade = None
        self.hide()

    def is_running(self) -> bool:
        return self.isVisible()

    def start(self, track, src: QRectF, dst: QRectF, src_radius: float, dst_radius: float,
              src_border: int = 0, dst_border: int = 0, fade_out=None, on_done=None):
        """Fly `track`'s cover from `src` to `dst` (rectangles in this widget's coordinates).
        fade_out: optional (QImage, QPointF) picture that fades away while the cover flies."""
        self.finish()
        size = -(-int(ceil(max(src.width(), dst.width()))) // 32) * 32  # in steps of 32, like the Player's cover
        self._px = CoverRenderer.pixmap(track, max(32, size), 0)  # corners are cut while painting (radius moves)
        self._src, self._dst = src, dst
        self._radius = (src_radius, dst_radius)
        self._border = (src_border, dst_border)
        self._fade = fade_out
        self._on_done = on_done
        self._t = 0.0
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self._anim.start()

    def finish(self):
        """Ends the flight at once (no-op when idle); the caller's on_done puts the real covers back."""
        if not self.isVisible():
            return
        self._anim.stop()
        self.hide()
        self._fade = None
        done, self._on_done = self._on_done, None
        self.progressChanged.emit(1.0)
        if done:
            done()

    def _step(self, v):
        self._t = float(v)
        self.progressChanged.emit(self._t)
        self.update()

    def paintEvent(self, e):
        if self._px is None:
            return
        t = self._t
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if self._fade is not None:
            img, pos = self._fade
            p.setOpacity(max(0.0, 1.0 - t * 1.6))  # the mini player is gone a bit before the cover lands
            p.drawImage(pos, img)
            p.setOpacity(1.0)
        s, d = self._src, self._dst
        r = QRectF(_lerp(s.x(), d.x(), t), _lerp(s.y(), d.y(), t), _lerp(s.width(), d.width(), t),
                   _lerp(s.height(), d.height(), t))
        rad = _lerp(self._radius[0], self._radius[1], t)
        lift = sin(pi * t)  # 0 at both ends, 1 half way: the cover rises a little while it travels
        p.setPen(Qt.NoPen)
        for k in range(1, 7):  # soft shadow
            g = r.adjusted(-k * 3, -k * 3 + 6, k * 3, k * 3 + 6)
            p.setBrush(QColor(0, 0, 0, int(16 * lift)))
            p.drawRoundedRect(g, rad + k * 3, rad + k * 3)
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)
        p.save()
        p.setClipPath(path)
        p.drawPixmap(r, self._px, QRectF(self._px.rect()))
        p.restore()
        alpha = int(_lerp(self._border[0], self._border[1], t))
        if alpha:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, alpha), 1))
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), rad, rad)
