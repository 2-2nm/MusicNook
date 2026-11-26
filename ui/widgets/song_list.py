import math
import time

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QMenu, QPushButton,
                               QStyle, QStyledItemDelegate, QVBoxLayout, QWidget)

from models.track_list_model import TrackListModel
from services.cover_service import CoverService
from ui import theme
from ui.backdrop import paint_backdrop
from ui.smooth_scroll import SmoothListView

ROW_H = 46
COVER = 34
PAD = 12
FADE_H = 90  # height of the bottom fade in px
SORTS = {"added": "Date added", "title": "Title", "artist": "Artist", "album": "Album"}


def columns(w: int) -> dict:
    """Column x-positions as fractions of the row width (shared by header and rows)."""
    return {"title": PAD + COVER + 12, "album": int(w * 0.50), "added": int(w * 0.74),
            "quality": int(w * 0.82), "time_right": w - 12}


class TrackDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_id = None
        self.playing = False    # the equalizer bars only move while music is playing
        self.cover_rect = None  # where the playing row's cover was last painted (viewport coords), for cheap repaints
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
            self.cover_rect = QRect(r.x() + PAD, cy, COVER, COVER)
            now = time.monotonic()
            for i, still in enumerate((8, 15, 11)):
                if self.playing:  # each bar bounces at its own pace, so it never looks like a loop of one shape
                    wave = 0.5 + 0.5 * math.sin(now * (5.2 + 1.7 * i) + i * 2.1)
                    h = 4 + 12 * wave
                else:
                    h = still
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
        if hasattr(central, "paint_into"):
            central.paint_into(q)  # exactly what the window paints behind it, tint and pattern included
        else:
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

    def __init__(self, model: TrackListModel, sorts: dict | None = None, heading: str = "All songs", parent=None):
        super().__init__(parent)
        self.model = model
        self.sorts = sorts or SORTS
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # Section title + Sort / Filter / Select buttons
        top = QHBoxLayout()
        title = QLabel(heading)
        title.setFont(theme.font(22, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{theme.TEXT};")
        top.addWidget(title)
        top.addStretch(1)
        self.sort_btn = QPushButton("Sort: " + next(iter(self.sorts.values())))
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
        self._eq_timer = QTimer(self, interval=40)  # drives the equalizer bars on the playing row
        self._eq_timer.timeout.connect(self._tick_eq)
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

        # Sort menu
        sort_menu = QMenu(self)
        for key, label in self.sorts.items():
            sort_menu.addAction(label, lambda k=key: self._set_sort(k))
        self.sort_btn.setMenu(sort_menu)

        # Filter menu (rebuilt each time it opens, from the formats currently in the library)
        self.filter_menu = QMenu(self)
        self.filter_menu.aboutToShow.connect(self._build_filter_menu)
        self.filter_btn.setMenu(self.filter_menu)

        self.select_btn.toggled.connect(self._toggle_select)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # Keep the fade pinned to the bottom of the list view
        v = self.view.geometry()
        self.fade.setGeometry(v.x(), v.bottom() - FADE_H + 1, v.width(), FADE_H)

    def reset(self, sort_key: str):
        """Back to a clean view: no filter, no selection, the given sort."""
        self.select_btn.setChecked(False)
        self.model.set_query("")
        self.model.set_formats(set())
        self.filter_btn.setText("Filter")
        self._set_sort(sort_key)

    def _set_sort(self, key: str):
        self.model.set_sort(key)
        self.sort_btn.setText(f"Sort: {self.sorts[key]}")

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

    def set_playing(self, playing: bool):
        """Equalizer bars on the current row move while music plays and freeze when it is paused."""
        self.delegate.playing = playing
        if playing:
            self._eq_timer.start()
        else:
            self._eq_timer.stop()
        self.view.viewport().update()

    def _tick_eq(self):
        # Repaint only the cover of the playing row. The delegate re-arms cover_rect whenever that row is painted,
        # so nothing is repainted (and the timer costs nothing) while the row is scrolled out of view.
        rect, self.delegate.cover_rect = self.delegate.cover_rect, None
        if rect is not None:
            self.view.viewport().update(rect)

    def set_current(self, track_id):
        """Highlight the row of the currently playing track."""
        self.delegate.current_id = track_id
        self.view.viewport().update()