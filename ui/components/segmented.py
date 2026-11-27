from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QWidget

# The buttons are transparent; the highlighted capsule is a separate widget behind them that slides.
_STYLE = """
QPushButton#segSlide{background:transparent;border:none;border-radius:17px;padding:0 20px;color:#aab0c8;font-size:15px;font-weight:600;}
QPushButton#segSlide:checked{color:#ffffff;}
QPushButton#segSlide:hover:!checked{color:#ffffff;}
"""


class _Pill(QWidget):
    """The highlighted capsule behind the active tab."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 36))  # same as the old checked tab: rgba(255,255,255,0.14)
        r = self.height() / 2
        p.drawRoundedRect(self.rect(), r, r)


class SegmentedTabs(QFrame):
    """Capsule tab bar (looks like the old QPushButton#seg tabs). The highlight glides to the tab that is picked."""
    idClicked = Signal(int)  # only when the user clicks a tab, not when it is set from code

    def __init__(self, names, height: int = 42, stretch: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("segFrame")  # frame look from theme.STYLE
        self.setFixedHeight(height)
        self.setStyleSheet(_STYLE)
        self._pill = _Pill(self)  # created first, so the buttons are stacked above it
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        for i, name in enumerate(names):
            b = QPushButton(name)
            b.setObjectName("segSlide")
            b.setCheckable(True)
            b.setFixedHeight(height - 8)
            b.setCursor(Qt.PointingHandCursor)
            self._group.addButton(b, i)
            lay.addWidget(b, 1 if stretch else 0)
        self._group.button(0).setChecked(True)
        self._group.idClicked.connect(self._clicked)
        self._anim = QPropertyAnimation(self._pill, b"geometry", self)
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def current(self) -> int:
        return self._group.checkedId()

    def set_current(self, i: int, animate: bool = False):
        """Pick a tab from code. The highlight glides only when animate is True and the bar is on screen."""
        self._group.button(i).setChecked(True)
        self._move(animate)

    def _clicked(self, i: int):
        self._move(True)
        self.idClicked.emit(i)

    def _target(self) -> QRect:
        b = self._group.checkedButton()
        return b.geometry() if b is not None else QRect()

    def _snap(self):
        self._anim.stop()
        self.layout().activate()
        self._pill.setGeometry(self._target())
        self._pill.setVisible(self._group.checkedButton() is not None)

    def _move(self, animate: bool):
        target = self._target()
        if not animate or not self.isVisible() or not self._pill.isVisible() or target.isNull():
            self._snap()
            return
        self._anim.stop()
        self._anim.setStartValue(self._pill.geometry())
        self._anim.setEndValue(target)
        self._anim.start()

    def showEvent(self, e):
        super().showEvent(e)
        self._snap()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._snap()