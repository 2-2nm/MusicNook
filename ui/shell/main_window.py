import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QMainWindow, QVBoxLayout

from app import config
from data.db import Database
from services.collection_service import (PLAYLIST_EMPTY, SMART_EMPTY, SMART_NAMES, CollectionService)
from services.library_service import LibraryService
from services.play_tracker import PlayTracker
from services.player_service import PlayerService
from services.playlist_service import PlaylistService
from services.session_service import SessionService
from ui.components.corner_close import CornerClose
from ui.components.fade_stack import FadeStack
from ui.components.track_list_model import TrackListModel
from ui.pages.library import LibraryPage
from ui.pages.now_playing import NowPlayingPage
from ui.pages.playlists import CollectionPage, PlaylistsPage
from ui.pages.playlists.cover import custom_pixmap, mosaic_tracks, playlist_tint
from ui.shell import frameless
from ui.shell.backdrop import Backdrop
from ui.shell.cover_flight import CoverFlight
from ui.shell.cover_flight_controller import CoverFlightController
from ui.shell.header import LibraryHeader
from ui.shell.mini_player import MiniPlayer
from ui.shell.navigation import Page
from ui.shell.playlist_actions import PlaylistActions
from ui.shell.sidebar import Sidebar
from ui.shell.window_state import WindowStateMixin


class MainWindow(WindowStateMixin, QMainWindow):
    """Shell of the app: builds the pages, connects them to the services and switches between them.
    Cover flight, playlist dialogs, session restore and play counting live in their own classes."""

    def __init__(self):
        super().__init__()
        self._init_window_state()
        self.setWindowTitle(config.APP_NAME)
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
        self.settings = config.new_settings()
        self._restore_window_state()  # remembered size / position / maximized, like NPI Gallery
        self.db = Database()
        self.library = LibraryService(self.db, self)
        self.player = PlayerService(self)
        self.playlists = PlaylistService(self.db, self)
        self.collections = CollectionService(self.library)
        self.session = SessionService(self.settings, self.player)
        self.play_tracker = PlayTracker(self.player, self.library)
        self.model = TrackListModel(self)
        self._all = []
        self._playlist_items = []
        self._page = Page.LIBRARY
        self._lib_tab = 0  # Library header tab: 0 Songs, 1 Albums
        self._albums = []
        self._collection = None  # ("smart", 0..3) or ("playlist", id) while its page is open
        self._coll_title, self._coll_stats = "", ""
        self._coll_tint = None  # glow colour of the open playlist / collection (from its cover)
        self._build_ui()
        self.actions = PlaylistActions(self, self.playlists, self.player, lambda: self._playlist_items,
                                       self._open_playlist_id)
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
        self.now_tab = tab if tab in (NowPlayingPage.TAB_QUEUE, NowPlayingPage.TAB_LYRICS,
                                      NowPlayingPage.TAB_INFO) else NowPlayingPage.TAB_QUEUE

        vol = self.session.volume()
        self.player.set_volume(vol)
        self.mini.set_volume(vol)
        self.songs.set_sort(self.session.sort())  # the sort of the last session
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

        self.lib_page = LibraryPage(self.model)
        self.card, self.recent, self.songs = self.lib_page.card, self.lib_page.recent, self.lib_page.songs
        self.albums_view = self.lib_page.albums
        self.mini = MiniPlayer()  # shared footer: shown on Library and Playlists, hidden on Player
        self.now_page = NowPlayingPage(self.player)
        self.playlists_page = PlaylistsPage()
        self.collection_page = CollectionPage()
        self.pages = FadeStack(duration=260)  # fade_to() is used when the cover flies between a page and Player
        for page in (self.lib_page, self.now_page, self.playlists_page, self.collection_page):  # order = Page
            self.pages.addWidget(page)
        right.addWidget(self.pages, 1)
        right.addSpacing(4)  # keep the gap between the list fade and the mini player small
        right.addWidget(self.mini)
        root.addLayout(right, 1)

        # Close button floats above the caption pill and reaches the window corner
        self.corner_close = CornerClose(central)
        self.corner_close.clicked.connect(self.close)
        self._flight = CoverFlight(central)  # the cover gliding between Library / Playlists and Player
        self.flyer = CoverFlightController(self, self._flight)

    def _wire(self):
        self._wire_player()
        self._wire_library()
        self._wire_playlists()
        self._wire_navigation()

    def _wire_player(self):
        p, m = self.player, self.mini
        p.trackChanged.connect(self._on_track)
        p.positionChanged.connect(self._on_position)
        p.durationChanged.connect(lambda _: self._on_position(p.position()))
        p.playingChanged.connect(m.set_playing)
        p.playingChanged.connect(self.card.set_playing)
        p.playingChanged.connect(self.songs.set_playing)
        p.playingChanged.connect(self.collection_page.songs.set_playing)
        p.volumeChanged.connect(m.set_volume)
        m.prevClicked.connect(p.prev)
        m.nextClicked.connect(p.next)
        m.toggleClicked.connect(p.toggle)
        m.seekRequested.connect(p.seek_ratio)
        m.volumeChanged.connect(p.set_volume)
        m.openRequested.connect(self._open_now_playing)
        self.now_page.accentChanged.connect(self._on_accent)
        self.now_page.tabChanged.connect(self._on_tab)

    def _wire_library(self):
        p = self.player
        self.card.seekRequested.connect(p.seek_ratio)
        self.card.resumeClicked.connect(self._resume)
        self.card.shuffleClicked.connect(lambda: p.shuffle_all(self._all))
        self.recent.trackClicked.connect(lambda t: p.play_queue([t], 0))
        self.songs.rowActivated.connect(lambda row: p.play_queue(self.model.visible_tracks(), row))
        self.songs.sortPicked.connect(self.session.set_sort)
        self.songs.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.songs.view.customContextMenuRequested.connect(
            lambda pos: self.actions.song_menu(self.songs, self.model, pos))
        self.header.searchChanged.connect(self._on_search)
        self.header.tabChanged.connect(self._on_lib_tab)
        av = self.albums_view
        av.playRequested.connect(lambda tracks, i: p.play_queue(tracks, i))
        av.shuffleRequested.connect(p.shuffle_all)
        av.queueRequested.connect(p.enqueue)
        self.sidebar.addFolderRequested.connect(self.add_folder)
        self.library.statsChanged.connect(self._refresh_smart)
        self.library.changed.connect(lambda: self._reload_timer.start())

    def _wire_playlists(self):
        pp, cp = self.playlists_page, self.collection_page
        self.header.newPlaylistClicked.connect(lambda: self.actions.new_playlist())
        pp.newRequested.connect(lambda: self.actions.new_playlist())
        pp.playRequested.connect(self.actions.play)
        pp.editRequested.connect(self.actions.edit)
        pp.deleteRequested.connect(self.actions.delete)
        pp.smartRequested.connect(lambda k: self._open_collection("smart", k))
        pp.openRequested.connect(lambda pid: self._open_collection("playlist", pid))
        cp.backClicked.connect(lambda: self.sidebar.nav_playlists.click())
        cp.playClicked.connect(lambda: self._play_collection(False))
        cp.shuffleClicked.connect(lambda: self._play_collection(True))
        cp.rowActivated.connect(lambda row: self.player.play_queue(cp.model.visible_tracks(), row))
        cp.songs.view.setContextMenuPolicy(Qt.CustomContextMenu)
        cp.songs.view.customContextMenuRequested.connect(
            lambda pos: self.actions.song_menu(cp.songs, cp.model, pos))
        self.playlists.changed.connect(self._refresh_playlists)

    def _wire_navigation(self):
        self.sidebar.pageSelected.connect(self._on_page)

    # ---------- data ----------
    def reload(self):
        self._all = self.library.tracks()
        self.model.set_tracks(self._all)
        self._albums = self.collections.albums(self._all)
        self.albums_view.set_albums(self._albums)
        self._refresh_lib_subtitle()
        self.recent.set_tracks(self.collections.recent_albums(self._all))
        self._refresh_playlists()

    def _refresh_lib_subtitle(self):
        if self._lib_tab == 1:
            artists = len({a.artist for a in self._albums})
            n = len(self._albums)
            self.header.set_stats_text(f"{n} album{'' if n == 1 else 's'} \u00b7 {artists} artist{'' if artists == 1 else 's'}")
        else:
            self.header.set_stats(len(self._all), sum(t.duration for t in self._all))

    def _on_lib_tab(self, i: int):
        self._lib_tab = i
        self.lib_page.set_tab(i)
        self._refresh_lib_subtitle()

    def _refresh_playlists(self):
        by_id = {t.id: t for t in self._all}
        self._playlist_items = [(pl, [by_id[i] for i in self.playlists.track_ids(pl.id) if i in by_id])
                                for pl in self.playlists.all()]
        self.playlists_page.set_data(self._playlist_items)
        self._refresh_smart()
        self.sidebar.set_counts(len(self._all), len(self._playlist_items))
        self._refresh_collection("playlist")
        if self._page == Page.PLAYLISTS:
            self._apply_page()

    def _refresh_smart(self):
        self.playlists_page.set_smart_counts([len(self.collections.smart_tracks(k, self._all)) for k in range(4)])
        self._refresh_collection("smart")

    # ---------- collection page ----------
    def _open_playlist_id(self):
        """Id of the playlist whose page is open (None on any other page or for a smart collection)."""
        if self._page == Page.COLLECTION and self._collection and self._collection[0] == "playlist":
            return self._collection[1]
        return None

    def _open_collection(self, kind: str, key: int):
        self._collection = (kind, key)
        if self._load_collection():
            self._on_page(Page.COLLECTION)

    def _load_collection(self, reset: bool = True) -> bool:
        """Fill the collection page from whatever is open. False (and back to Playlists) if it is gone."""
        kind, key = self._collection
        if kind == "smart":
            title, tracks, empty = SMART_NAMES[key], self.collections.smart_tracks(key, self._all), SMART_EMPTY[key]
            desc = ""
            custom = None
            extra = self.collections.smart_extra(key, tracks)
        else:
            found = next(((pl, t) for pl, t in self._playlist_items if pl.id == key), None)
            if found is None:
                self._collection = None
                self.sidebar.nav_playlists.click()
                return False
            title, tracks, empty = found[0].name, found[1], PLAYLIST_EMPTY
            desc = found[0].description
            custom = custom_pixmap(found[0].cover)
            extra = None
        self._coll_tint = playlist_tint(mosaic_tracks(tracks), custom, (kind, key))
        self._coll_title = title
        self._coll_stats = self.collections.stats_text(tracks)
        cp = self.collection_page
        cp.set_tracks(tracks, empty, reset, extra)
        cp.set_description(desc)
        cur = self.player.current
        cp.songs.set_current(cur.id if cur else None)
        cp.songs.set_playing(self.player.is_playing())
        return True

    def _refresh_collection(self, kind: str):
        """The data behind the open page changed (a play was counted, a playlist was edited ...)."""
        if self._page == Page.COLLECTION and self._collection and self._collection[0] == kind:
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

    # ---------- navigation ----------
    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose music folder", str(Path.home() / "Music"))
        if folder:
            self.library.scan(folder)

    def _open_now_playing(self):
        """Clicking the mini player at the bottom opens Player (same as the sidebar item)."""
        if self.player.current:
            self.flyer.via_mini = True
            self.sidebar.nav_now.click()
            self.flyer.via_mini = False

    def _on_page(self, i: int):
        old, self._page = self._page, Page(i)
        self.flyer.finish()
        if self.flyer.can_fly(old, self._page):
            self.flyer.fly(old, self._page)
        else:
            self.pages.setCurrentIndex(self._page)
            self.mini.setVisible(self._page != Page.PLAYER)
            if self._page == Page.PLAYER:
                self.now_page.show_tab(self.now_tab)  # Player: back to the tab the user left it on
        self._apply_page()

    def _on_search(self, q: str):
        if self._page == Page.PLAYLISTS:
            self.playlists_page.set_query(q)
        else:
            self.model.set_query(q)
            self.albums_view.set_query(q)

    def _on_tab(self, i: int):
        # Remember the tab picked on the Player page (the Queue page does not change the choice)
        if self._page == Page.PLAYER:
            self.now_tab = i
            self.settings.setValue("now_playing/tab", i)

    def _apply_page(self):
        page = self._page
        backdrop = self.centralWidget()
        backdrop.set_pattern(page)  # the glow glides to this page's place
        if page == Page.PLAYER:
            self.header.set_page("Player", "Playing from Library", tabs=False, search=False)
        elif page == Page.PLAYLISTS:
            self.header.set_page("Playlists", f"{len(self._playlist_items)} playlists \u00b7 4 smart collections",
                                 tabs=False, placeholder="Search playlists", action=True)
        elif page == Page.COLLECTION:
            self.header.set_page(self._coll_title, self._coll_stats, tabs=False, search=False)
        else:
            self.header.set_page("Library")
        backdrop.set_tint(self._page_tint(), glide=True)

    def _page_tint(self):
        """Glow colour of the page on screen: the player's own colour on Player, the cover colour of the playlist
        on its page (the playing track's colour while that has no cover), the playing track's colour elsewhere."""
        if self._page == Page.PLAYER:
            return self.now_page.accent
        if self._page == Page.COLLECTION and self._coll_tint is not None:
            return self._coll_tint
        return self._library_tint()

    def _library_tint(self):
        """The Library follows the playing track's colour too; with nothing loaded it keeps the plain backdrop."""
        return self.now_page.accent if self.player.current else None

    def _on_accent(self, color):
        self.card.set_accent(self._library_tint())  # Continue listening follows the cover colour too
        self.centralWidget().set_tint(self._page_tint())

    # ---------- playback ----------
    def _resume(self):
        # The card's main button: Pause while playing, Resume when paused, otherwise start the list
        if self.player.is_playing():
            self.player.pause()
        elif self.player.current:
            self.player.play()
        elif self.model.rowCount():
            self.player.play_queue(self.model.visible_tracks(), 0)

    def _on_track(self, t):
        self.flyer.finish()  # the flying cover would be the old song's
        self.play_tracker.reset()
        self.collection_page.songs.set_current(t.id)
        self.mini.set_track(t)
        self.card.set_track(t)
        self.songs.set_current(t.id)
        self.albums_view.set_current(t.id)
        if self._page != Page.LIBRARY:
            self._apply_page()

    def _on_position(self, pos: int):
        cur = self.player.current
        dur = self.player.duration() or (int(cur.duration * 1000) if cur else 0)
        self.mini.set_progress(pos, dur)
        self.card.set_progress(pos, dur)
        self.play_tracker.update(cur, pos, dur)

    def _restore_last(self):
        pos = self.session.restore(self._all, self.model.visible_tracks())
        if pos is not None:
            self._on_position(pos)

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
        if hasattr(self, "flyer"):
            self.flyer.finish()  # its start and end points belong to the old size
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
        self.session.save()
        super().closeEvent(e)