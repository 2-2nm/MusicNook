from PySide6.QtCore import QCoreApplication, QEasingCurve, QEvent, QObject, QVariantAnimation
from PySide6.QtWidgets import QWidget

from ui.components.fade_stack import _Blend, snapshot


class Crossfade(QObject):
    """Cross-fades one widget's content when `change` swaps it (the same blend FadeStack uses for Tracks -> Lyrics).
    `target` is the widget that is pictured; `content` is what really changes inside it and is hidden while the
    two pictures blend."""

    def __init__(self, target: QWidget, content: QWidget, duration: int = 220):
        super().__init__(target)
        self._target, self._content = target, content
        self._blend = None
        self._anim = QVariantAnimation(self, duration=duration)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._step)
        self._anim.finished.connect(self.finish)

    def run(self, change):
        self.finish()  # a fade still running is completed first, so quick clicks never stack up
        if not self._target.isVisible():
            change()
            return
        old = snapshot(self._target)
        change()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)  # lay the new content out before it is pictured
        new = snapshot(self._target)
        self._content.hide()
        self._blend = _Blend(self._target, old, new)
        self._blend.setGeometry(self._target.rect())
        self._blend.show()
        self._blend.raise_()
        self._anim.start()

    def _step(self, v):
        if self._blend is not None:
            self._blend.set_progress(float(v))

    def finish(self):
        if self._blend is None:
            return
        self._anim.stop()
        blend, self._blend = self._blend, None
        self._content.show()  # the real content takes over from the picture in the same step
        blend.hide()
        blend.deleteLater()
