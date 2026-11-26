from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QMenu, QPushButton,
                               QStyle, QStyledItemDelegate, QVBoxLayout, QWidget)

from models.track_list_model import TrackListModel
from services.cover_service import CoverService
from ui import theme
from ui.backdrop import paint_backdrop
from ui.smooth_scroll import SmoothListView
from ui.widgets.alpha_index import AlphaIndex

ROW_H = 46
COVER = 34
PAD = 12
FADE_H = 90  # height of the bottom fade in px
INDEX_W = 22  # width reserved at the right edge for the A-Z index overlay
SORTS = {"added": "Date added", "title": "Title", "artist": "Artist", "album": "Album"}


def columns(w: int) -> dict:
    """Column x-positions as fractions of the row width (shared by header and rows)."""
    return {"title": PAD + COVER + 12, "album": int(w * 0.50), "added": int(w * 0.74),
            "quality": int(w * 0.82), "time_right": w - INDEX_W - 12}


class TrackDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_id = None
        W = QFont.Weight
        self.f_title = theme.font(14, W.DemiBold)
        self.f_sub = theme.font(12)
        self.f_col = theme.font(13)
        self.f_pill = theme.font(11, W.DemiBold)

    def sizeHint(self, opt, index):
        return QSize(opt.rect.width(), ROW_H)

    def paint(self, p, opt, index):
        t = index.data(TrackListModel.TrackRole)
        r = opt.rect
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        playing = t.id == self.current_id
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        hover = bool(opt.state & QStyle.StateFlag.State_MouseOver)

        # Row background: accent tint for the playing row, subtle white for hover/selection
        if playing or selected or hover:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(90, 120, 255, 42) if playing else QColor(255, 255, 255, 28 if selected else 12))
            p.drawRoundedRect(QRectF(r).adjusted(0, 2, 0, -2), 14, 14)

        # Cover art
        cy = r.y() + (r.height() - COVER) // 2
        p.drawPixmap(r.x() + PAD, cy, CoverService.pixmap(t, COVER, 8))

        # "Now playing" equalizer bars drawn over the cover
        if playing:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 90))
            p.drawRoundedRect(QRectF(r.x() + PAD, cy, COVER, COVER), 8, 8)
            p.setBrush(QColor("#ffffff"))
            for i, h in enumerate((8, 15, 11)):
                p.drawRoundedRect(QRectF(r.x() + PAD + 10 + i * 5, cy + (COVER + 15) / 2 - h, 3, h), 1.5, 1.5)

        c = columns(r.width())
        x0, y0 = r.x(), r.y()

        # Title + artist
        maxw = c["album"] - c["title"] - 16
        p.setFont(self.f_title)
        p.setPen(QColor(theme.ACCENT if playing else theme.TEXT))
        p.drawText(QRectF(x0 + c["title"], y0 + 6, maxw, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(t.title, Qt.ElideRight, maxw))
        p.setFont(self.f_sub)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(x0 + c["title"], y0 + 25, maxw, 16), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(t.artist, Qt.ElideRight, maxw))

        # Album, date added, duration
        p.setFont(self.f_col)
        p.setPen(QColor("#c4c9de"))
        aw = c["added"] - c["album"] - 16
        p.drawText(QRectF(x0 + c["album"], y0, aw, r.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(t.album, Qt.ElideRight, aw))
        p.drawText(QRectF(x0 + c["added"], y0, 80, r.height()), Qt.AlignLeft | Qt.AlignVCenter,
                   theme.fmt_added(t.added))
        p.drawText(QRectF(x0, y0, c["time_right"], r.height()), Qt.AlignRight | Qt.AlignVCenter,
                   theme.fmt_time(t.duration * 1000))

        # Quality pill (MP3 / FLAC / ...)
        p.setFont(self.f_pill)
        pw = p.fontMetrics().horizontalAdvance(t.fmt) + 20
        pill = QRectF(x0 + c["quality"], y0 + (r.height() - 24) / 2, pw, 24)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 24))
        p.drawRoundedRect(pill, 7, 7)
        p.setPen(QColor("#d6dbf2"))
        p.drawText(pill, Qt.AlignCenter, t.fmt)
        p.restore()


class ColumnHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setFont(theme.font(11, QFont.Weight.Medium, 1.6))
        p.setPen(QColor(theme.DIM))
        c = columns(self.width())
        h = self.height() - 4
        for key, text in (("title", "TITLE"), ("album", "ALBUM"), ("added", "ADDED"), ("quality", "QUALITY")):
            p.drawText(QRectF(c[key], 0, 120, h), Qt.AlignLeft | Qt.AlignVCenter, text)
        p.drawText(QRectF(0, 0, c["time_right"], h), Qt.AlignRight | Qt.AlignVCenter, "TIME")
        # Bottom divider line
        p.setPen(QColor(255, 255, 255, 22))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


class FadeOverlay(QWidget):
    """Repaints the real window backdrop with an alpha that grows downward,
    so the song rows dissolve into the background without a visible color band."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

    def paintEvent(self, e):
        central = self.window().centralWidget()
        if central is None:
            return
        dpr = self.devicePixelRatioF()
        w, h = self.width(), self.height()

        # Render the matching slice of the backdrop into an offscreen image
        img = QImage(int(w * dpr), int(h * dpr), QImage.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(0)
        q = QPainter(img)
        off = self.mapTo(central, QPoint(0, 0))
        q.translate(-off.x(), -off.y())
        paint_backdrop(q, central.width(), central.height())
        q.resetTransform()

        # Multiply by a vertical alpha ramp: transparent at the top, opaque at the bottom
        q.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0, QColor(0, 0, 0, 0))
        g.setColorAt(0.55, QColor(0, 0, 0, 150))
        g.setColorAt(1.0, QColor(0, 0, 0, 255))
        q.fillRect(QRectF(0, 0, w, h), g)
        q.end()

        QPainter(self).drawImage(0, 0, img)


class SongList(QWidget):
    rowActivated = Signal(int)

    def __init__(self, model: TrackListModel, parent=None):
        super().__init__(parent)
        self.model = model
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # Section title + Sort / Filter / Select buttons
        top = QHBoxLayout()
        title = QLabel("All songs")
        title.setFont(theme.font(22, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{theme.TEXT};")
        top.addWidget(title)
        top.addStretch(1)
        self.sort_btn = QPushButton("Sort: Date added")
        self.filter_btn = QPushButton("Filter")
        self.select_btn = QPushButton("Select")
        self.select_btn.setCheckable(True)
        for b in (self.sort_btn, self.filter_btn, self.select_btn):
            b.setObjectName("pill")
            b.setFixedHeight(36)
            b.setCursor(Qt.PointingHandCursor)
            top.addWidget(b)
        lay.addLayout(top)
        lay.addWidget(ColumnHeader())

        # List view (scrollbar hidden so row widths line up with the column header)
        # Wheel glides like NPI Gallery; the list scrolls FADE_H past its last row so the fade never hides it
        self.view = SmoothListView(bottom_padding=FADE_H)
        self.view.setModel(model)
        self.delegate = TrackDelegate(self.view)
        self.view.setItemDelegate(self.delegate)
        self.view.setUniformItemSizes(True)
        self.view.setMouseTracking(True)
        self.view.setSelectionMode(QAbstractItemView.NoSelection)
        self.view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # One click plays a song. In Select mode a click selects the row instead, and a double click plays it.
        self.view.clicked.connect(self._on_clicked)
        self.view.doubleClicked.connect(self._on_double_clicked)
        lay.addWidget(self.view, 1)

        # Fade sits on top of the list's bottom edge
        self.fade = FadeOverlay(self)
        self.fade.raise_()

        # A-Z index overlays the right edge of the list, so the content keeps one shared right edge
        self.alpha = AlphaIndex(self)
        self.alpha.letterClicked.connect(self.jump_to_letter)
        self.alpha.raise_()

        # Sort menu
        sort_menu = QMenu(self)
        for key, label in SORTS.items():
            sort_menu.addAction(label, lambda k=key: self._set_sort(k))
        self.sort_btn.setMenu(sort_menu)

        # Filter menu (rebuilt each time it opens, from the formats currently in the library)
        self.filter_menu = QMenu(self)
        self.filter_menu.aboutToShow.connect(self._build_filter_menu)
        self.filter_btn.setMenu(self.filter_menu)

        self.select_btn.toggled.connect(self._toggle_select)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # Keep the fade pinned to the bottom of the list view, and the index along its right edge
        v = self.view.geometry()
        self.fade.setGeometry(v.x(), v.bottom() - FADE_H + 1, v.width(), FADE_H)
        self.alpha.setGeometry(v.right() - INDEX_W + 1, v.y() + 8, INDEX_W, max(0, v.height() - FADE_H // 2 - 8))
        self.alpha.raise_()

    def _set_sort(self, key: str):
        self.model.set_sort(key)
        self.sort_btn.setText(f"Sort: {SORTS[key]}")

    def _build_filter_menu(self):
        self.filter_menu.clear()
        for fmt in self.model.available_formats():
            a = self.filter_menu.addAction(fmt)
            a.setCheckable(True)
            a.setChecked(fmt in self.model.formats)
            a.toggled.connect(lambda on, f=fmt: self._toggle_format(f, on))

    def _toggle_format(self, fmt: str, on: bool):
        s = set(self.model.formats)
        s.add(fmt) if on else s.discard(fmt)
        self.model.set_formats(s)
        self.filter_btn.setText(f"Filter ({len(s)})" if s else "Filter")

    def _on_clicked(self, index):
        if not self.select_btn.isChecked():
            self.rowActivated.emit(index.row())

    def _on_double_clicked(self, index):
        if self.select_btn.isChecked():
            self.rowActivated.emit(index.row())

    def _toggle_select(self, on: bool):
        self.view.setSelectionMode(QAbstractItemView.MultiSelection if on else QAbstractItemView.NoSelection)
        if not on:
            self.view.clearSelection()

    def set_current(self, track_id):
        """Highlight the row of the currently playing track."""
        self.delegate.current_id = track_id
        self.view.viewport().update()

    def jump_to_letter(self, letter: str):
        """Scroll to the first title starting with `letter` (switches to title sort if needed)."""
        if self.model.sort_key != "title":
            self._set_sort("title")
        row = self.model.first_row_for_letter(letter)
        if row >= 0:
            self.view.scroll_to(row * ROW_H)  # rows are uniform, so this puts the row at the top (and glides there)