from bisect import bisect_right
from math import ceil, floor

from PySide6.QtCore import QEasingCurve, QRect, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget

from ui import theme
from ui.components.smooth_scroll import SCROLL_ANIMATION_MS, WHEEL_PIXELS_PER_NOTCH, FrameAnimation, WheelInput

BASE = 20       # px: font size every line is laid out (and wrapped) at
MAX_SCALE = 1.4  # the active line is drawn at BASE * MAX_SCALE (= 28 px)
GAP = 20        # px between lines (measured at the line's own scale)
PAD = 6         # left / right padding
EDGE_FADE = 90  # px: lines only fade out over this distance at the top / bottom edge of the view
RESUME_MS = 3000  # after this long without scrolling, the view glides back to the playing line


class LyricsView(QWidget):
    """Synced lyrics: the active line is big and white, the others fade out with distance.

    A line that is wider than the panel wraps onto the next row(s) and pushes the lines below it down.
    Every line is wrapped once at the base size and then only *scaled* for the active-line effect, so the
    wrapping never reflows while the view scrolls.

    The wheel scrolls the lyrics freely (browse mode, same glide as the song list). The view follows the
    song again once the user has stopped scrolling for RESUME_MS, or as soon as a line is clicked."""
    seekRequested = Signal(int)  # ms, when a line is clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines: list[tuple[int, str]] = []
        self._times: list[int] = []
        self._idx = -1
        self._pos = 0.0  # scroll position in "lines"
        self._heights: list[int] | None = None  # wrapped height of each line at BASE size
        self._hits: list[tuple[int, float, float]] = []  # (line, top, bottom) from the last paint
        self._anim = QVariantAnimation(self, duration=380)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

        # browse mode: the user scrolls, so the view is anchored to `_anchor` (in lines) instead of the active line
        self._browsing = False
        self._resuming = False
        self._anchor = 0.0
        self._glide_from = 0.0
        self._glide_target = 0.0
        self._glide = FrameAnimation(self, SCROLL_ANIMATION_MS, QEasingCurve(QEasingCurve.Type.OutCubic))
        self._glide.valueChanged.connect(self._on_glide)
        self._glide.finished.connect(self._on_glide_done)
        self._wheel_input = WheelInput()
        self._resume_timer = QTimer(self, singleShot=True, interval=RESUME_MS)
        self._resume_timer.timeout.connect(self._resume)

    def set_lines(self, lines: list[tuple[int, str]]):
        self._lines = lines
        self._times = [t for t, _ in lines]
        self._idx = -1
        self._heights = None
        self._hits = []
        self._anim.stop()
        self._glide.stop()
        self._resume_timer.stop()
        self._browsing = self._resuming = False
        self._pos = 0.0
        self.setCursor(Qt.PointingHandCursor if lines else Qt.ArrowCursor)
        self.update()

    def set_position(self, ms: int):
        if not self._lines:
            return
        i = max(0, bisect_right(self._times, ms + 150) - 1)
        if i != self._idx:
            self._idx = i
            self._anim.stop()
            self._anim.setStartValue(float(self._pos))
            self._anim.setEndValue(float(i))
            self._anim.start()

    def _on_anim(self, v):
        self._pos = float(v)
        self.update()

    # ---------- layout ----------
    def _wrap_width(self) -> int:
        # Narrow enough that the active line, scaled up by MAX_SCALE, still fits the panel
        return max(40, int((self.width() - 2 * PAD) / MAX_SCALE))

    def _font(self) -> QFont:
        return theme.font(BASE, QFont.Weight.DemiBold)

    def _measure(self) -> list[int]:
        if self._heights is None:
            fm = QFontMetrics(self._font())
            w = self._wrap_width()
            self._heights = [
                fm.boundingRect(QRect(0, 0, w, 100000), int(Qt.TextWordWrap | Qt.AlignLeft), text).height()
                for _, text in self._lines
            ]
        return self._heights

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._heights = None  # wrapping depends on the width

    def _scale(self, i: int) -> float:
        return 1.0 + (MAX_SCALE - 1.0) * max(0.0, 1.0 - abs(i - self._pos))

    def _anchor_pos(self) -> float:
        return self._anchor if self._browsing else self._pos

    def _move(self, pos: float, px: float) -> float:
        """`pos` (in lines) moved by `px` pixels of lyrics (positive = further down the song), clamped."""
        hs = self._measure()
        n = len(hs)
        pos = min(max(pos, 0.0), n - 1.0)
        while px and n > 1:
            if px > 0:
                i = int(floor(pos))
                if i + 1 >= n:
                    return n - 1.0
                d = (hs[i] + hs[i + 1]) / 2 + GAP  # distance between the centres of line i and i + 1
                room = d * (i + 1 - pos)
                if px < room:
                    return pos + px / d
                px -= room
                pos = float(i + 1)
            else:
                i = int(ceil(pos))
                if i - 1 < 0:
                    return 0.0
                d = (hs[i - 1] + hs[i]) / 2 + GAP
                room = d * (pos - (i - 1))
                if -px < room:
                    return pos + px / d
                px += room
                pos = float(i - 1)
        return pos

    def _layout(self) -> list[tuple[int, float, float]]:
        """[(line, top, height)] for every line near the viewport, in widget coordinates."""
        n = len(self._lines)
        hs = self._measure()
        h = self.height()
        pos = min(max(self._anchor_pos(), 0.0), n - 1.0)
        i0 = min(int(floor(pos)), n - 1)
        frac = pos - i0

        def height_of(i):
            return hs[i] * self._scale(i)

        # tops relative to line i0; the scroll anchor is between the centres of i0 and i0 + 1
        rel = {i0: 0.0}
        i, y = i0, 0.0
        while i + 1 < n:
            y += height_of(i) + GAP * self._scale(i)
            i += 1
            rel[i] = y
            if y > h * 2:
                break
        i, y = i0, 0.0
        while i - 1 >= 0:
            i -= 1
            y -= height_of(i) + GAP * self._scale(i)
            rel[i] = y
            if -y > h * 2:
                break

        c0 = rel[i0] + height_of(i0) / 2
        c1 = (rel[i0 + 1] + height_of(i0 + 1) / 2) if (i0 + 1) in rel else c0
        anchor = c0 + frac * (c1 - c0)
        shift = h / 2 - anchor

        out = []
        for i, top in sorted(rel.items()):
            t, hh = top + shift, height_of(i)
            if t + hh < -20 or t > h + 20:
                continue
            out.append((i, t, hh))
        return out

    # ---------- painting ----------
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if not self._lines:
            self._hits = []
            p.setFont(theme.font(18, QFont.Weight.DemiBold))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(0, h / 2 - 34, w, 30), Qt.AlignCenter, "No lyrics found")
            p.setFont(theme.font(13))
            p.setPen(QColor(theme.DIM))
            p.drawText(QRectF(20, h / 2 - 2, w - 40, 44), Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
                       "Put a synced .lrc file next to the song or in a lyrics folder.")
            return
        p.setFont(self._font())
        ww = self._wrap_width()
        hs = self._measure()
        self._hits = []
        for i, top, hh in self._layout():
            k = max(0.0, 1.0 - abs(i - self._pos))  # 1 on the active line
            # fade by pixels from the top / bottom edge (not by number of lines), so a tall panel is filled
            edge = h / 2 - abs(top + hh / 2 - h / 2)  # distance of the line's centre from the nearest edge
            t = min(1.0, max(0.0, edge / min(EDGE_FADE, h / 4)))
            fade = t * t * (3 - 2 * t)  # smoothstep
            s = self._scale(i)
            self._hits.append((i, top - GAP * s / 2, top + hh + GAP * s / 2))
            alpha = int(255 * (0.36 + 0.64 * k) * fade)
            if alpha <= 0:
                continue
            p.save()
            p.translate(PAD, top)
            p.scale(s, s)
            p.setPen(QColor(255, 255, 255, alpha))
            p.drawText(QRectF(0, 0, ww, hs[i]), int(Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop), self._lines[i][1])
            p.restore()

    def mousePressEvent(self, e):
        if not self._lines or e.button() != Qt.LeftButton:
            return
        y = e.position().y()
        for i, top, bottom in self._hits:
            if top <= y < bottom:
                self.seekRequested.emit(self._times[i])
                if self._browsing:
                    self._resume_timer.stop()
                    self._resume()  # go back to following the song right away
                return

    # ---------- scrolling ----------
    def wheelEvent(self, e):
        if not self._lines or e.modifiers() or e.angleDelta().y() == 0:
            e.ignore()
            return
        if not self._browsing:
            self._browsing = True
            self._anchor = self._pos
        self._resuming = False
        if self._wheel_input.is_precision(e):  # touchpad: scroll the content directly
            self._glide.stop()
            self._anchor = self._move(self._anchor, -self._wheel_input.pixels(e))
            self.update()
        else:  # mouse wheel: glide, quick notches stack onto the running glide
            base = self._glide_target if self._glide.isRunning() else self._anchor
            self._glide_to(self._move(base, -round(e.angleDelta().y() * WHEEL_PIXELS_PER_NOTCH / 120)))
        self._resume_timer.start()
        e.accept()

    def _glide_to(self, target: float):
        self._glide_from = self._anchor
        self._glide_target = target
        self._glide.stop()
        if target != self._anchor:
            self._glide.start()

    def _on_glide(self, progress: float):
        self._anchor = self._glide_from + (self._glide_target - self._glide_from) * progress
        self.update()

    def _on_glide_done(self):
        if self._resuming:
            self._finish_resume()

    def _resume(self):
        """Glide back to the line that is playing, then follow the song again."""
        if not self._browsing:
            return
        self._resuming = True
        target = float(max(0, self._idx))
        if abs(self._anchor - target) < 1e-3:
            self._glide.stop()
            self._finish_resume()
        else:
            self._glide_to(target)

    def _finish_resume(self):
        self._resuming = False
        self._browsing = False
        self.update()