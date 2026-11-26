import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, QSettings, QTimer, Qt
from PySide6.QtGui import QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

from models.track_list_model import TrackListModel
from services.library_service import LibraryService
from services.player_service import PlayerService
from ui import frameless
from ui.backdrop import paint_backdrop
from ui.widgets.continue_card import ContinueCard
from ui.widgets.corner_close import CornerClose
from ui.widgets.header import LibraryHeader
from ui.widgets.mini_player import MiniPlayer
from ui.widgets.recent_row import RecentRow
from ui.widgets.sidebar import Sidebar
from ui.widgets.song_list import SongList
from ui.window_state import WindowStateMixin


class Backdrop(QWidget):
    """Central widget: paints the window background behind the floating cards.

    ClickFocus makes a click on any part that cannot take focus itself (labels, cards, the caption pill, the
    window buttons) land here, so the search box loses focus instead of staying in "searching" mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def paintEvent(self, e):
        p = QPainter(self)
        paint_backdrop(p, self.width(), self.height())


class MainWindow(WindowStateMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self._init_window_state()
        self.setWindowTitle("NPI Audio")
        if frameless.IS_WINDOWS and sys.getwindowsversion().build >= frameless.WIN11_BUILD:
            # Same as NPI Gallery's main window: on Windows 11 the window is translucent (set before the
            # native window exists). The central widget paints everything opaque, so nothing changes
            # visually, but Windows then treats the window like the gallery's and animates minimize/restore.
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Windows keeps its native frame (animations, Aero snap, resize borders) and only the
        # title bar is removed in nativeEvent; other platforms fall back to a frameless window.
        if not frameless.IS_WINDOWS:
            self.setWindowFlag(Qt.FramelessWindowHint, True)
        self._frame_applied = False
        self._grips = []
        self.resize(1210, 756)
        self.setMinimumSize(980, 620)
        self.settings = QSettings("AudioPlayer", "AudioPlayer")
        self._restore_window_state()  # remembered size / position / maximized, like NPI Gallery
        self.library = LibraryService(self)
        self.player = PlayerService(self)
        self.model = TrackListModel(self)
        self._build_ui()
        self._grips = frameless.build_grips(self)
        self._ui_ready = True
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        self._wire()
        self._reload_timer = QTimer(self, singleShot=True, interval=300)
        self._reload_timer.timeout.connect(self.reload)

        vol = float(self.settings.value("volume", 0.75))
        self.player.set_volume(vol)
        self.mini.set_volume(vol)
        self.reload()
        self._restore_last()
        if not self._all:
            music = Path.home() / "Music"
            if music.exists():
                self.library.scan(str(music))
            else:
                QTimer.singleShot(400, self.add_folder)

    # ---------- ui ----------
    def _build_ui(self):
        central = Backdrop()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(20)

        self.sidebar = Sidebar()
        root.addWidget(self.sidebar)

        # Right side: header and content share the same right edge, so everything lines up
        # with the caption pill in the corner (the alpha index overlays the song list).
        right = QVBoxLayout()
        right.setSpacing(0)
        self.header = LibraryHeader()
        right.addWidget(self.header)
        right.addSpacing(18)

        left = QVBoxLayout()
        left.setSpacing(0)
        top = QHBoxLayout()
        top.setSpacing(36)
        self.card = ContinueCard()
        self.recent = RecentRow()
        top.addWidget(self.card, 1)
        top.addWidget(self.recent)
        left.addLayout(top)
        left.addSpacing(18)
        self.songs = SongList(self.model)
        left.addWidget(self.songs, 1)
        left.addSpacing(4)  # keep the gap between the list fade and the mini player small
        self.mini = MiniPlayer()
        left.addWidget(self.mini)
        right.addLayout(left, 1)
        root.addLayout(right, 1)

        # Close button floats above the caption pill and reaches the window corner
        self.corner_close = CornerClose(central)
        self.corner_close.clicked.connect(self.close)

    def _wire(self):
        p, m = self.player, self.mini
        p.trackChanged.connect(self._on_track)
        p.positionChanged.connect(self._on_position)
        p.durationChanged.connect(lambda _: self._on_position(p.position()))
        p.playingChanged.connect(m.set_playing)
        p.playingChanged.connect(self.card.set_playing)
        p.volumeChanged.connect(m.set_volume)
        m.prevClicked.connect(p.prev)
        m.nextClicked.connect(p.next)
        m.toggleClicked.connect(p.toggle)
        m.seekRequested.connect(p.seek_ratio)
        m.volumeChanged.connect(p.set_volume)
        self.card.seekRequested.connect(p.seek_ratio)
        self.card.resumeClicked.connect(self._resume)
        self.card.shuffleClicked.connect(lambda: p.shuffle_all(self._all))
        self.recent.trackClicked.connect(lambda t: p.play_queue([t], 0))
        self.songs.rowActivated.connect(lambda row: p.play_queue(self.model.visible_tracks(), row))
        self.header.searchChanged.connect(self.model.set_query)
        self.sidebar.addFolderRequested.connect(self.add_folder)
        self.library.changed.connect(lambda: self._reload_timer.start())

    # ---------- behaviour ----------
    def reload(self):
        self._all = self.library.tracks()
        self.model.set_tracks(self._all)
        self.header.set_stats(len(self._all), sum(t.duration for t in self._all))
        self.sidebar.set_counts(len(self._all), len(self.player.queue))
        seen, recent = set(), []
        for t in sorted(self._all, key=lambda t: t.added, reverse=True):
            if t.album_key not in seen:
                seen.add(t.album_key)
                recent.append(t)
        self.recent.set_tracks(recent)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose music folder", str(Path.home() / "Music"))
        if folder:
            self.library.scan(folder)

    def _resume(self):
        # The card's main button: Pause while playing, Resume when paused, otherwise start the list
        if self.player.is_playing():
            self.player.pause()
        elif self.player.current:
            self.player.play()
        elif self.model.rowCount():
            self.player.play_queue(self.model.visible_tracks(), 0)

    def _on_track(self, t):
        self.mini.set_track(t)
        self.card.set_track(t)
        self.songs.set_current(t.id)
        self.sidebar.set_counts(len(self._all), len(self.player.queue))

    def _on_position(self, pos: int):
        cur = self.player.current
        dur = self.player.duration() or (int(cur.duration * 1000) if cur else 0)
        self.mini.set_progress(pos, dur)
        self.card.set_progress(pos, dur)

    def _restore_last(self):
        tid = self.settings.value("last_track_id")
        if tid is None or not self._all:
            return
        queue = self.model.visible_tracks()
        for i, t in enumerate(queue):
            if t.id == int(tid):
                pos = int(self.settings.value("last_position", 0))
                self.player.restore(queue, i, pos)
                self._on_position(pos)
                return

    # ---------- frameless window ----------
    def _place_close(self):
        if not self._ui_ready:
            return
        slot = self.header.controls.close_slot
        central = self.centralWidget()
        if central is None or not slot.isVisible():
            return
        pos = slot.mapTo(central, QPoint(0, 0))
        self.corner_close.place(pos.x(), pos.y(), central.width())
        self.corner_close.raise_()

    def _is_caption_at(self, p: QPoint) -> bool:
        """True where a drag should move the window: the top band outside any real control."""
        bar_bottom = self.header.mapTo(self, QPoint(0, self.header.height())).y()
        if p.y() >= bar_bottom:
            return False
        child = self.childAt(p)
        if child is None or child is self.centralWidget() or child is self.header:
            return True
        return isinstance(child, QLabel) or bool(child.property("dragRegion"))

    def _is_client_at(self, p: QPoint) -> bool:
        """The close button (including its stretch into the corner) must win over the resize grips."""
        if not self.corner_close.isVisible():
            return False
        rect = QRect(self.corner_close.mapTo(self, QPoint(0, 0)), self.corner_close.size())
        return rect.contains(p)

    def _on_caption_press(self):
        """A press on the drag area is a native (non-client) click that Qt never sees as a mouse press."""
        search = getattr(getattr(self, "header", None), "search", None)
        if search is not None and search.hasFocus() and self.centralWidget() is not None:
            self.centralWidget().setFocus(Qt.FocusReason.MouseFocusReason)

    def nativeEvent(self, event_type, message):
        result = frameless.handle_native_event(
            self, event_type, message, self._is_caption_at, self._is_client_at, self._on_caption_press
        )
        if result is not None:
            return result
        return super().nativeEvent(event_type, message)

    def showEvent(self, e):
        super().showEvent(e)
        if frameless.IS_WINDOWS and not self._frame_applied:
            self._frame_applied = True
            frameless.apply_frame(self)
            frameless.round_corners(self)
        QTimer.singleShot(0, self._place_close)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        frameless.place_grips(self, self._grips)
        frameless.refresh_corner_region(self)
        self._place_close()
        QTimer.singleShot(0, self._place_close)  # once the layout has settled

    def changeEvent(self, e):
        super().changeEvent(e)
        # restoreGeometry-like state changes can fire before the widgets exist
        if e.type() == QEvent.Type.WindowStateChange and hasattr(self, "header"):
            self.header.controls.set_maximized(self.isMaximized())
            frameless.place_grips(self, self._grips)
            # Never touch the frame while the minimize / restore animation is running
            if frameless.IS_WINDOWS and not self.isMinimized():
                QTimer.singleShot(0, self._refresh_frame)

    def _refresh_frame(self):
        """Re-read the frame once the new window state has settled, so no stale inset remains."""
        if frameless.IS_WINDOWS and self.isVisible() and not self.isMinimized():
            frameless.ensure_system_menu(self)  # Qt drops it in full screen, which kills the minimize animation
            frameless.apply_frame(self)
            frameless.refresh_corner_region(self)
            self._place_close()

    def closeEvent(self, e):
        self._save_window_state()
        self.player.pause()
        cur = self.player.current
        if cur:
            self.settings.setValue("last_track_id", cur.id)
            self.settings.setValue("last_position", self.player.position())
        self.settings.setValue("volume", self.player.volume())
        super().closeEvent(e)