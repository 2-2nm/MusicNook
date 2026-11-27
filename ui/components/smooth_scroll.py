"""Mouse-wheel glide for scroll views, ported from NPI Gallery (gui/common/motion.py).

WheelInput, FrameAnimation and SmoothWheelMixin are the gallery's own blueprint with the same constants,
so the song list scrolls with the same feel: each wheel notch moves a fixed distance, quick notches stack
onto the running glide, and touchpads (which already send smooth pixel deltas) scroll the content directly.
"""

import time

from PySide6.QtCore import QEasingCurve, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QAbstractItemView, QListView, QScrollArea

# One notch moves this many pixels and the view glides there (same values as the gallery).
WHEEL_PIXELS_PER_NOTCH = 130
SCROLL_ANIMATION_MS = 170

# Touchpads report many small angleDeltas and no pixelDelta; they scroll the content directly, scaled by this.
TOUCHPAD_SCROLL_SCALE = 0.45
_NOTCH = 120
_PRECISION_STREAM_MS = 200  # events this close after a touchpad event are still the touchpad


class WheelInput:
    """Tells a classic mouse wheel from a touchpad and turns touchpad deltas into pixels.

    A classic wheel always reports whole multiples of 120. Touchpads report fine-grained deltas (or
    pixelDelta), so any other value marks the event as precision. Once a precision event is seen, the events
    right after it count as precision too, so a stray multiple of 120 mid-swipe is not mistaken for a mouse.
    """

    def __init__(self) -> None:
        self._last_precision = 0.0
        self._remainder = 0.0

    def is_precision(self, event) -> bool:
        now = time.monotonic()
        delta = event.angleDelta().y() or event.angleDelta().x()
        precision = (
            not event.pixelDelta().isNull()
            or event.phase() != Qt.ScrollPhase.NoScrollPhase
            or (delta != 0 and delta % _NOTCH != 0)
        )
        if precision:
            self._last_precision = now
            return True
        return (now - self._last_precision) * 1000.0 < _PRECISION_STREAM_MS

    def pixels(self, event) -> int:
        """Touchpad delta as whole pixels to scroll (sign: positive = content moves down)."""
        raw = event.pixelDelta().y() if not event.pixelDelta().isNull() else event.angleDelta().y()
        self._remainder += raw * TOUCHPAD_SCROLL_SCALE
        whole = int(self._remainder)  # truncate toward zero, keep the fraction for the next event
        self._remainder -= whole
        return whole


class FrameAnimation(QObject):
    """Time-based 0->1 animation that ticks at the screen's refresh rate (60, 120, 144 Hz...).

    Qt's own animations are capped at ~60 fps. This one asks the timer for one tick per display refresh and
    derives its value from the clock, so a slow frame never slows the motion down. valueChanged carries the
    eased value; finished fires only when it reaches the end.
    """

    valueChanged = Signal(float)
    finished = Signal()

    def __init__(self, parent: QObject | None, duration: int, curve: QEasingCurve, start: float = 0.0, end: float = 1.0):
        super().__init__(parent)
        self._duration = max(1, int(duration))
        self._curve = curve
        self._from = float(start)
        self._to = float(end)
        self._started = 0.0
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)

    def isRunning(self) -> bool:
        return self._timer.isActive()

    def _interval(self) -> int:
        screen = None
        getter = getattr(self.parent(), "screen", None)
        if callable(getter):
            screen = getter()
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        rate = float(screen.refreshRate()) if screen is not None else 60.0
        if rate < 30.0:
            rate = 60.0
        return max(4, int(round(1000.0 / min(rate, 240.0))))

    def start(self) -> None:
        self._started = time.perf_counter()
        self._timer.start(self._interval())

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        progress = (time.perf_counter() - self._started) * 1000.0 / self._duration
        if progress >= 1.0:
            self._timer.stop()
            self.valueChanged.emit(self._to)
            self.finished.emit()
            return
        eased = float(self._curve.valueForProgress(progress))
        self.valueChanged.emit(self._from + (self._to - self._from) * eased)


class SmoothWheelMixin:
    """Mouse-wheel glide for any scroll area (QListView, QScrollArea, QTreeView...).

    Dragging the scroll bar stops the glide so they never fight it. Call `_init_glide()` once from __init__,
    after the base class is constructed. Views that scroll per item must be switched to ScrollPerPixel.
    """

    def _init_glide(self) -> None:
        self._glide_from = 0
        self._glide_target = 0
        self._glide = FrameAnimation(self, SCROLL_ANIMATION_MS, QEasingCurve(QEasingCurve.Type.OutCubic))
        self._glide.valueChanged.connect(self._on_glide)
        self.verticalScrollBar().actionTriggered.connect(lambda *_: self._glide.stop())
        self._wheel_input = WheelInput()

    def _on_glide(self, progress: float) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(round(self._glide_from + (self._glide_target - self._glide_from) * progress))

    def scroll_to(self, value: int) -> None:
        """Glide to `value` (clamped to the scroll range)."""
        bar = self.verticalScrollBar()
        self._glide_target = max(bar.minimum(), min(bar.maximum(), int(value)))
        self._glide_from = bar.value()
        self._glide.stop()
        if self._glide_target == self._glide_from:
            return
        self._glide.start()

    def wheelEvent(self, event) -> None:
        if event.modifiers() or event.angleDelta().y() == 0:
            super().wheelEvent(event)
            return
        bar = self.verticalScrollBar()
        if bar.maximum() <= bar.minimum():
            event.ignore()  # nothing to scroll
            return
        if self._wheel_input.is_precision(event):
            self._glide.stop()
            bar.setValue(bar.value() - self._wheel_input.pixels(event))
            event.accept()
            return
        base = self._glide_target if self._glide.isRunning() else bar.value()
        self.scroll_to(base - round(event.angleDelta().y() * WHEEL_PIXELS_PER_NOTCH / 120))
        event.accept()


class SmoothListView(SmoothWheelMixin, QListView):
    """QListView whose mouse wheel glides instead of jumping a few rows at a time.

    `bottom_padding` lets the list scroll that many pixels past its last row, so something drawn over the
    bottom edge (the song list's fade) never has to cover the last rows for good.
    """

    def __init__(self, parent=None, bottom_padding: int = 0):
        super().__init__(parent)
        self._bottom_padding = max(0, int(bottom_padding))
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._init_glide()

    def updateGeometries(self) -> None:
        super().updateGeometries()  # Qt (re)computes the scroll range here: after a resize and after the rows change
        self._pad_bottom()

    def _pad_bottom(self) -> None:
        model = self.model()
        if not self._bottom_padding or model is None or model.rowCount() == 0:
            return
        bar = self.verticalScrollBar()
        content = model.rowCount() * max(1, self.sizeHintForRow(0))  # uniform rows
        wanted = max(bar.maximum(), content + self._bottom_padding - self.viewport().height())
        if wanted != bar.maximum():
            bar.setMaximum(wanted)

    # A press must land on the row under the cursor, so a glide still running is stopped first (otherwise
    # the row moves between press and release and the click is lost). Keyboard navigation does the same.
    def mousePressEvent(self, event) -> None:
        self._glide.stop()
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        self._glide.stop()
        super().keyPressEvent(event)


class SmoothScrollArea(SmoothWheelMixin, QScrollArea):
    """QScrollArea (album grid, track list of an album ...) with the same wheel glide as the song list."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_glide()

    def keyPressEvent(self, event) -> None:
        self._glide.stop()
        super().keyPressEvent(event)
