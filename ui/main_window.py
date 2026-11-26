import sys
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QRect, QSettings, QTimer, QVariantAnimation, Qt
from PySide6.QtGui import QColor, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMenu, QStackedWidget, QVBoxLayout, QWidget

from models.track_list_model import TrackListModel
from services.library_service import LibraryService
from services.player_service import PlayerService
from services.playlist_service import PlaylistService
from ui import frameless
from ui.backdrop import paint_backdrop
from ui.now_playing import NowPlayingPage
from ui.playlist import CollectionPage, PlaylistsPage
from ui.playlist.dialogs import ask_name, confirm, edit_playlist
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
    window buttons) land here, so the search box loses focus instead of staying in "searching" mode.

    The cover-colour glow has two animated parts besides the colour itself: `mode` (Library pattern <-> player
    pattern) and `strength` (tint on / off), so changing page or starting the first song glides instead of snapping."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tint = None
        self._mode = 0.0       # 0 = Library pattern, 1 = Now playing pattern
        self._strength = 0.0   # 0 = plain backdrop, 1 = full tint
        self._mode_goal = 0.0
        self._strength_goal = 0.0
        self._mode_anim = self._make_anim(self._set_mode)
        self._strength_anim = self._make_anim(self._set_strength)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def _make_anim(self, setter):
        a = QVariantAnimation(self, duration=550)
        a.setEasingCurve(QEasingCurve.Type.InOutCubic)
        a.valueChanged.connect(setter)
        return a

    def _set_mode(self, v):
        self._mode = float(v)
        self.update()

    def _set_strength(self, v):
        self._strength = float(v)
        self.update()

    @staticmethod
    def _glide(anim, current: float, goal: float):
        anim.stop()
        anim.setStartValue(float(current))
        anim.setEndValue(float(goal))
        anim.start()

    def set_tint(self, color):
        """Cover colour of the playing track. None fades the tint out (the last colour is kept while it does)."""
        if color is not None:
            self._tint = QColor(color)
            if self._strength_goal != 1.0:
                self._strength_goal = 1.0
                self._glide(self._strength_anim, self._strength, 1.0)
        elif self._strength_goal != 0.0:
            self._strength_goal = 0.0
            self._glide(self._strength_anim, self._strength, 0.0)
        self.update()

    def set_player_mode(self, on: bool):
        """True on the Now playing / Queue pages, False on the Library: glides between the two glow patterns."""
        goal = 1.0 if on else 0.0
        if goal != self._mode_goal:
            self._mode_goal = goal
            self._glide(self._mode_anim, self._mode, goal)

    def paint_into(self, painter):
        paint_backdrop(painter, self.width(), self.height(), self._tint, self._mode, self._strength)

    def paintEvent(self, e):
        p = QPainter(self)
        self.paint_into(p)


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
        self.playlists = PlaylistService(self.library.db_path, self)
        self.model = TrackListModel(self)
        self._playlist_items = []
        self._counted_id = None  # track whose play has already been counted
        self._collection = None  # ("smart", 0..3) or ("playlist", id) while its page is open
        self._coll_title, self._coll_stats = "", ""
        self._build_ui()
        self._grips = frameless.build_grips(self)
        self._ui_ready = True
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)
        self._wire()
        self._reload_timer = QTimer(self, singleShot=True, interval=300)
        self._reload_timer.timeout.connect(self.reload)

        try:
            tab = int(self.settings.value("now_playing/tab", NowPlayingPage.TAB_QUEUE))
        except (TypeError, ValueError):
            tab = NowPlayingPage.TAB_QUEUE
        self._now_tab = tab if tab in (NowPlayingPage.TAB_QUEUE, NowPlayingPage.TAB_LYRICS,
                                       NowPlayingPage.TAB_INFO) else NowPlayingPage.TAB_QUEUE

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
        # with the caption pill in the corner.
        right = QVBoxLayout()
        right.setSpacing(0)
        self.header = LibraryHeader()
        right.addWidget(self.header)
        right.addSpacing(18)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
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
        self.mini = MiniPlayer()  # shared footer: shown on Library and Playlists, hidden on Now playing
        # Pages: 0 = library (everything above), 1 = Now playing (ui/now_playing), 2 = Playlists
        self.lib_page = QWidget()
        self.lib_page.setLayout(left)
        self.now_page = NowPlayingPage(self.player)
        self.pages = QStackedWidget()
        self.pages.addWidget(self.lib_page)
        self.pages.addWidget(self.now_page)
        self.playlists_page = PlaylistsPage()
        self.pages.addWidget(self.playlists_page)
        self.collection_page = CollectionPage()
        self.pages.addWidget(self.collection_page)
        right.addWidget(self.pages, 1)
        right.addSpacing(4)  # keep the gap between the list fade and the mini player small
        right.addWidget(self.mini)
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
        p.playingChanged.connect(self.songs.set_playing)
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
        self.header.searchChanged.connect(self._on_search)
        self.header.newPlaylistClicked.connect(lambda: self.new_playlist())
        pp = self.playlists_page
        pp.newRequested.connect(lambda: self.new_playlist())
        pp.playRequested.connect(self._play_playlist)
        pp.editRequested.connect(self._edit_playlist)
        pp.deleteRequested.connect(self._delete_playlist)
        pp.smartRequested.connect(lambda k: self._open_collection("smart", k))
        pp.openRequested.connect(lambda pid: self._open_collection("playlist", pid))
        cp = self.collection_page
        cp.backClicked.connect(lambda: self.sidebar.nav_playlists.click())
        cp.playClicked.connect(lambda: self._play_collection(False))
        cp.shuffleClicked.connect(lambda: self._play_collection(True))
        cp.rowActivated.connect(lambda row: p.play_queue(cp.model.visible_tracks(), row))
        p.playingChanged.connect(cp.songs.set_playing)
        cp.songs.view.setContextMenuPolicy(Qt.CustomContextMenu)
        cp.songs.view.customContextMenuRequested.connect(lambda pos: self._song_menu(cp.songs, cp.model, pos))
        self.library.statsChanged.connect(self._refresh_smart)
        self.playlists.changed.connect(self._refresh_playlists)
        self.songs.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.songs.view.customContextMenuRequested.connect(lambda pos: self._song_menu(self.songs, self.model, pos))
        self.sidebar.addFolderRequested.connect(self.add_folder)
        self.sidebar.pageSelected.connect(self._on_page)
        m.openRequested.connect(self._open_now_playing)
        self.now_page.accentChanged.connect(self._on_accent)
        self.now_page.tabChanged.connect(self._on_tab)
        self.library.changed.connect(lambda: self._reload_timer.start())

    # ---------- behaviour ----------
    def reload(self):
        self._all = self.library.tracks()
        self.model.set_tracks(self._all)
        self.header.set_stats(len(self._all), sum(t.duration for t in self._all))
        seen, recent = set(), []
        for t in sorted(self._all, key=lambda t: t.added, reverse=True):
            if t.album_key not in seen:
                seen.add(t.album_key)
                recent.append(t)
        self.recent.set_tracks(recent)
        self._refresh_playlists()

    # ---------- playlists ----------
    def _refresh_playlists(self):
        by_id = {t.id: t for t in self._all}
        self._playlist_items = [(pl, [by_id[i] for i in self.playlists.track_ids(pl.id) if i in by_id])
                                for pl in self.playlists.all()]
        self.playlists_page.set_data(self._playlist_items)
        self._refresh_smart()
        self.sidebar.set_counts(len(self._all), len(self._playlist_items))
        self._refresh_collection("playlist")
        if getattr(self, "_page", 0) == 2:
            self._apply_page()

    # Smart collections, in the order of the cards: Favourites, Recently played, Most played, Recently added
    def _smart_tracks(self, kind: int) -> list:
        by_id = {t.id: t for t in self._all}
        if kind == 3:  # newest files first
            return sorted(self._all, key=lambda t: t.added, reverse=True)[:30]
        if kind == 0:  # Favourites: needs the heart button (not built yet)
            return []
        stats = {i: s for i, s in self.library.play_stats().items() if i in by_id and s[0] > 0}
        if kind == 1:  # most recently played first
            ids = sorted(stats, key=lambda i: stats[i][1], reverse=True)
        else:          # most plays first, ties broken by the more recent one
            ids = sorted(stats, key=lambda i: (stats[i][0], stats[i][1]), reverse=True)
        return [by_id[i] for i in ids[:50]]

    def _refresh_smart(self):
        self.playlists_page.set_smart_counts([len(self._smart_tracks(k)) for k in range(4)])
        self._refresh_collection("smart")

    SMART_NAMES = ("Favourites", "Recently played", "Most played", "Recently added")
    SMART_EMPTY = ("Favourites will show up here once you heart a song.",
                   "Songs you listen to will show up here.",
                   "Your most played songs will show up here.",
                   "No songs in your library yet.")
    PLAYLIST_EMPTY = "This playlist is empty. Right-click a song in your Library and choose Add to playlist."

    def _open_collection(self, kind: str, key: int):
        self._collection = (kind, key)
        if self._load_collection():
            self._on_page(3)

    def _load_collection(self, reset: bool = True) -> bool:
        """Fill the collection page from whatever is open. False (and back to Playlists) if it is gone."""
        kind, key = self._collection
        if kind == "smart":
            title, tracks, empty = self.SMART_NAMES[key], self._smart_tracks(key), self.SMART_EMPTY[key]
            desc = ""
        else:
            found = next(((pl, t) for pl, t in self._playlist_items if pl.id == key), None)
            if found is None:
                self._collection = None
                self.sidebar.nav_playlists.click()
                return False
            title, tracks, empty = found[0].name, found[1], self.PLAYLIST_EMPTY
            desc = found[0].description
        total = sum(t.duration for t in tracks)
        h, m = int(total // 3600), int(total % 3600 // 60)
        self._coll_title = title
        self._coll_stats = (f"{len(tracks)} song" + ("" if len(tracks) == 1 else "s")
                            + (f" \u00b7 {h} h {m} m" if tracks else ""))
        cp = self.collection_page
        cp.set_tracks(tracks, empty, reset)
        cp.set_description(desc)
        cur = self.player.current
        cp.songs.set_current(cur.id if cur else None)
        cp.songs.set_playing(self.player.is_playing())
        return True

    def _refresh_collection(self, kind: str):
        """The data behind the open page changed (a play was counted, a playlist was edited ...)."""
        if getattr(self, "_page", 0) == 3 and self._collection and self._collection[0] == kind:
            if self._load_collection(False):
                self._apply_page()

    def _play_collection(self, shuffle: bool):
        tracks = self.collection_page.model.visible_tracks()
        if not tracks:
            return
        if shuffle:
            self.player.shuffle_all(tracks)
        else:
            self.player.play_queue(tracks, 0)

    def _count_play(self, cur, pos: int, dur: int):
        """A play counts once it is actually playing and has reached 30 s (or half of a short track)."""
        if cur is None or self._counted_id == cur.id or not self.player.is_playing():
            return
        if pos >= (min(30000, dur // 2) if dur else 30000):
            self._counted_id = cur.id
            self.library.record_play(cur.id)

    def new_playlist(self, track_ids: list[int] | None = None):
        name = ask_name(self, "New playlist", "Give your playlist a name.",
                        f"Playlist {len(self._playlist_items) + 1}", "Create")
        if name:
            pid = self.playlists.create(name)
            if track_ids:
                self.playlists.add_tracks(pid, track_ids)

    def _play_playlist(self, pid: int):
        for pl, tracks in self._playlist_items:
            if pl.id == pid and tracks:
                self.player.play_queue(tracks, 0)
                return

    def _edit_playlist(self, pid: int):
        found = next(((pl, t) for pl, t in self._playlist_items if pl.id == pid), None)
        if found is None:
            return
        res = edit_playlist(self, *found)
        if res and res["name"]:
            self.playlists.update(pid, res["name"], res["description"], res["cover_src"], res["clear_cover"])

    def _delete_playlist(self, pid: int):
        cur = next((pl.name for pl, _ in self._playlist_items if pl.id == pid), "")
        if confirm(self, "Delete playlist", f"\u201c{cur}\u201d will be deleted. The songs stay in your library.",
                   "Delete", danger=True):
            self.playlists.delete(pid)

    def _song_menu(self, songs, model, pos):
        view = songs.view
        rows = []
        if songs.select_btn.isChecked():
            rows = sorted(ix.row() for ix in view.selectionModel().selectedRows())
        if not rows:
            ix = view.indexAt(pos)
            if not ix.isValid():
                return
            rows = [ix.row()]
        ids = [t.id for t in (model.track_at(r) for r in rows) if t]
        menu = QMenu(self)
        sub = menu.addMenu("Add to playlist")
        for pl, _ in self._playlist_items:
            sub.addAction(pl.name, lambda checked=False, pid=pl.id: self.playlists.add_tracks(pid, ids))
        if self._playlist_items:
            sub.addSeparator()
        sub.addAction("New playlist\u2026", lambda checked=False: self.new_playlist(ids))
        if getattr(self, "_page", 0) == 3 and self._collection and self._collection[0] == "playlist":
            pid = self._collection[1]
            menu.addAction("Remove from this playlist", lambda checked=False: self.playlists.remove_tracks(pid, ids))
        menu.exec(view.viewport().mapToGlobal(pos))

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose music folder", str(Path.home() / "Music"))
        if folder:
            self.library.scan(folder)

    def _open_now_playing(self):
        """Clicking the mini player at the bottom opens Now playing (same as the sidebar item)."""
        if self.player.current:
            self.sidebar.nav_now.click()

    def _on_page(self, i: int):
        self._page = i  # 0 = Library, 1 = Now playing, 2 = Playlists, 3 = one playlist / collection
        self.pages.setCurrentIndex(i)
        self.mini.setVisible(i != 1)
        if i == 1:
            self.now_page.show_tab(self._now_tab)  # Now playing: back to the tab the user left it on
        self._apply_page()

    def _on_search(self, q: str):
        if getattr(self, "_page", 0) == 2:
            self.playlists_page.set_query(q)
        else:
            self.model.set_query(q)

    def _on_tab(self, i: int):
        # Remember the tab picked on the Now playing page (the Queue page does not change the choice)
        if getattr(self, "_page", 0) == 1:
            self._now_tab = i
            self.settings.setValue("now_playing/tab", i)

    def _apply_page(self):
        i = getattr(self, "_page", 0)
        backdrop = self.centralWidget()
        backdrop.set_player_mode(i == 1)  # the glow pattern glides between Library and player
        if i == 1:
            self.header.set_page("Now playing", "Playing from Library", tabs=False, search=False)
            backdrop.set_tint(self.now_page.accent)
        elif i == 2:
            self.header.set_page("Playlists", f"{len(self._playlist_items)} playlists \u00b7 4 smart collections",
                                 tabs=False, placeholder="Search playlists", action=True)
            backdrop.set_tint(self._library_tint())
        elif i == 3:
            self.header.set_page(self._coll_title, self._coll_stats, tabs=False, search=False)
            backdrop.set_tint(self._library_tint())
        else:
            self.header.set_page("Library")
            backdrop.set_tint(self._library_tint())

    def _library_tint(self):
        """The Library follows the playing track's colour too; with nothing loaded it keeps the plain backdrop."""
        return self.now_page.accent if self.player.current else None

    def _on_accent(self, color):
        self.card.set_accent(self._library_tint())  # Continue listening follows the cover colour too
        if getattr(self, "_page", 0) == 1:
            self.centralWidget().set_tint(color)
        else:
            self.centralWidget().set_tint(self._library_tint())

    def _resume(self):
        # The card's main button: Pause while playing, Resume when paused, otherwise start the list
        if self.player.is_playing():
            self.player.pause()
        elif self.player.current:
            self.player.play()
        elif self.model.rowCount():
            self.player.play_queue(self.model.visible_tracks(), 0)

    def _on_track(self, t):
        self._counted_id = None
        self.collection_page.songs.set_current(t.id)
        self.mini.set_track(t)
        self.card.set_track(t)
        self.songs.set_current(t.id)
        if getattr(self, "_page", 0):
            self._apply_page()

    def _on_position(self, pos: int):
        cur = self.player.current
        dur = self.player.duration() or (int(cur.duration * 1000) if cur else 0)
        self.mini.set_progress(pos, dur)
        self.card.set_progress(pos, dur)
        self._count_play(cur, pos, dur)

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