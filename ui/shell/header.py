import sys

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ui import theme
from ui.icons import draw_icon
from ui.components.segmented import SegmentedTabs
from ui.components.window_controls import WindowControls

PILL_H = 42  # shared height of the tab pill, the search box and the caption pill
TAB_SHIFT_LEFT = 40  # px the tab capsule sits left of the exact middle of the header (0 = centered)


class SearchIcon(QWidget):
    """Magnifier drawn inside the search box (left padding in theme.STYLE leaves room for it)."""

    def __init__(self, box: QLineEdit):
        super().__init__(box)
        self._box = box
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setFixedSize(18, 18)
        self.move(18, (box.height() - 18) // 2)
        box.installEventFilter(self)

    def eventFilter(self, obj, e):
        if obj is self._box and e.type() in (e.Type.FocusIn, e.Type.FocusOut):
            self.update()  # brighter while typing
        return False

    def paintEvent(self, e):
        p = QPainter(self)
        draw_icon(p, "search", QRectF(self.rect()), "#c9d3ff" if self._box.hasFocus() else theme.MUTED)


class CapsuleButton(QAbstractButton):
    """Capsule button, painted by hand so the shape never depends on the style sheet.
    kind: "primary" = white, "secondary" = translucent, "danger" = red."""

    def __init__(self, text: str, kind: str = "primary", parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setText(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)
        self.setFixedHeight(PILL_H)
        self.setFixedWidth(theme_text_width(text) + 52)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(1.0 if self.isEnabled() else 0.4)
        r = QRectF(self.rect())
        hover = self.underMouse() and self.isEnabled()
        if self.kind == "primary":
            bg, fg = QColor("#e6e9ff" if hover else "#ffffff"), QColor("#0a0b14")
        elif self.kind == "danger":
            bg, fg = QColor("#ff7384" if hover else "#ff5468"), QColor("#ffffff")
        else:
            bg, fg = QColor(255, 255, 255, 51 if hover else 31), QColor(theme.TEXT)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setPen(fg)
        p.setFont(theme.font(15, QFont.Weight.DemiBold))
        p.drawText(r, Qt.AlignCenter, self.text())


def theme_text_width(text: str) -> int:
    from PySide6.QtGui import QFontMetrics
    return QFontMetrics(theme.font(15, QFont.Weight.DemiBold)).horizontalAdvance(text)


class LibraryHeader(QWidget):
    searchChanged = Signal(str)
    tabChanged = Signal(int)
    newPlaylistClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stats = "0 songs"
        self._library_mode = True
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        # Left and right groups get the same stretch, so the tab capsule always sits in the exact middle
        # of the free space, whatever the subtitle says ("96 albums" vs "1200 songs . 80 h 3 m").
        left_w = QWidget()
        left_w.setProperty("dragRegion", True)  # empty space in the bar still drags the window
        left = QVBoxLayout(left_w)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(0)
        self.title = title = QLabel("Library")
        title.setFont(theme.font(34, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{theme.TEXT};")
        self.subtitle = QLabel("0 songs")
        self.subtitle.setFont(theme.font(15))
        self.subtitle.setStyleSheet(f"color:{theme.MUTED};")
        left.addWidget(title)
        left.addWidget(self.subtitle)
        lay.addWidget(left_w, 1)

        # Every pill is top-aligned and PILL_H tall, so they all share one center line
        seg = SegmentedTabs(("Songs", "Albums", "Artists"), PILL_H)
        seg.idClicked.connect(self.tabChanged)
        self.seg = seg
        lay.addWidget(seg, 0, Qt.AlignTop)
        lay.addSpacing(TAB_SHIFT_LEFT * 2)  # the two equal groups share the rest, so this moves the capsule by half of it

        right_w = QWidget()
        right_w.setProperty("dragRegion", True)
        rlay = QHBoxLayout(right_w)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.addStretch(1)
        lay.addWidget(right_w, 1, Qt.AlignTop)

        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Search songs, albums, artists")
        self.search.setFixedSize(300, PILL_H)
        SearchIcon(self.search)
        self.search.textChanged.connect(self.searchChanged)
        rlay.addWidget(self.search, 0, Qt.AlignTop)
        # Page action ("+ New playlist"); the wrapper carries its left gap so nothing is left over when hidden
        self.action_wrap = QWidget()
        al = QHBoxLayout(self.action_wrap)
        al.setContentsMargins(12, 0, 0, 0)
        self.new_btn = CapsuleButton("+ New playlist", "primary")
        self.new_btn.clicked.connect(lambda: self.newPlaylistClicked.emit())
        al.addWidget(self.new_btn)
        self.action_wrap.hide()
        rlay.addWidget(self.action_wrap, 0, Qt.AlignTop)
        rlay.addSpacing(12)

        self.controls = WindowControls()
        self.controls.setFixedHeight(PILL_H)
        rlay.addWidget(self.controls, 0, Qt.AlignTop)

    def set_stats(self, count: int, total_seconds: float):
        h, m = int(total_seconds // 3600), int(total_seconds % 3600 // 60)
        self._stats = f"{count} songs · {h} h {m} m"
        if self._library_mode:
            self.subtitle.setText(self._stats)

    def set_stats_text(self, text: str):
        """Library subtitle of the active tab (e.g. \"96 albums \u00b7 58 artists\" on Albums)."""
        self._stats = text
        if self._library_mode:
            self.subtitle.setText(text)

    def set_page(self, title: str, subtitle: str | None = None, tabs: bool = True, search: bool = True,
                 placeholder: str | None = None, action: bool = False):
        """Switch the header between pages. subtitle=None keeps the library stats."""
        self._library_mode = subtitle is None
        self.title.setText(title)
        self.subtitle.setText(self._stats if subtitle is None else subtitle)
        self.seg.setVisible(tabs)
        self.search.setVisible(search)
        ph = placeholder or "Search songs, albums, artists"
        if ph != self.search.placeholderText():
            self.search.clear()  # a different page searches something else
            self.search.setPlaceholderText(ph)
        self.action_wrap.setVisible(action)

    # Non-Windows fallback only: on Windows dragging and double-click are handled natively (HTCAPTION)
    def mousePressEvent(self, e):
        if sys.platform != "win32" and e.button() == Qt.LeftButton:
            handle = self.window().windowHandle()
            if handle:
                handle.startSystemMove()
                return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        if sys.platform != "win32":
            w = self.window()
            w.showNormal() if w.isMaximized() else w.showMaximized()
            return
        super().mouseDoubleClickEvent(e)