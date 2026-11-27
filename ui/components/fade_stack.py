from PySide6.QtCore import QEasingCurve, QPoint, Qt, QVariantAnimation
from PySide6.QtGui import QImage, QPainter, QRegion
from PySide6.QtWidgets import QStackedWidget, QWidget


def snapshot(w: QWidget) -> QImage:
    """Picture of a page on a transparent background. Only the page and its children are drawn: no window
    background fill (the palette's dark Window colour is what showed up as a black flash in the translucent window)."""
    dpr = w.devicePixelRatioF()
    img = QImage(max(1, int(w.width() * dpr)), max(1, int(w.height() * dpr)), QImage.Format_ARGB32_Premultiplied)
    img.setDevicePixelRatio(dpr)
    img.fill(Qt.transparent)
    w.render(img, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
    return img


class _Blend(QWidget):
    """Draws the page that is leaving fading out and the page that is arriving fading in."""

    def __init__(self, parent, old: QImage, new: QImage):
        super().__init__(parent)
        self._old, self._new = old, new
        self._t = 0.0
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def set_progress(self, t: float):
        self._t = t
        self.update()

    def paintEvent(self, e):
        dpr = self.devicePixelRatioF()
        mix = QImage(max(1, int(self.width() * dpr)), max(1, int(self.height() * dpr)), QImage.Format_ARGB32_Premultiplied)
        mix.setDevicePixelRatio(dpr)
        mix.fill(Qt.transparent)
        q = QPainter(mix)  # mixed off screen first, so "plus" adds the two pages and not the window behind them
        q.setOpacity(1.0 - self._t)
        q.drawImage(0, 0, self._old)
        q.setCompositionMode(QPainter.CompositionMode_Plus)
        q.setOpacity(self._t)
        q.drawImage(0, 0, self._new)
        q.end()
        QPainter(self).drawImage(0, 0, mix)


class FadeStack(QStackedWidget):
    """QStackedWidget whose pages cross-fade when switched with fade_to(). setCurrentIndex() switches at once."""

    def __init__(self, parent=None, duration: int = 220):
        super().__init__(parent)
        self._anim = QVariantAnimation(self, duration=duration)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._step)
        self._anim.finished.connect(self._finish)
        self._blend = None
        self._page = None  # the page that is current but hidden while the two pictures blend

    def _set(self, index: int):
        QStackedWidget.setCurrentIndex(self, index)

    def setCurrentIndex(self, index: int):
        self._finish()
        self._set(index)

    def fade_to(self, index: int, prepare=None):
        """`prepare` (optional) runs after the picture of the old page was taken and before the new page is
        shown: use it for changes around the stack that resize it (they must not end up in the old picture)."""
        self._finish()  # a fade still running is completed first, so quick clicks never stack up
        if index == self.currentIndex():
            if prepare:
                prepare()
            return
        old = self.currentWidget()
        if old is None or not self.isVisible():
            if prepare:
                prepare()
            self._set(index)
            return
        old_img = snapshot(old)
        if prepare:
            prepare()
        self._set(index)  # shows the new page, which lays it out; nothing is painted before this method returns
        self._page = self.currentWidget()
        new_img = snapshot(self._page)
        self._page.hide()  # no real page while the two pictures blend (it stays the current one)
        self._blend = _Blend(self, old_img, new_img)
        self._blend.setGeometry(self.rect())
        self._blend.show()
        self._blend.raise_()
        self._anim.start()

    def _step(self, v):
        if self._blend is not None:
            self._blend.set_progress(float(v))

    def _finish(self):
        if self._blend is None:
            return
        self._anim.stop()
        blend, self._blend = self._blend, None
        self._page.show()  # the real page takes over from the picture in the same step
        self._page = None
        blend.hide()
        blend.deleteLater()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._blend is not None:
            self._blend.setGeometry(self.rect())