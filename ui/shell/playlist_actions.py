from PySide6.QtWidgets import QMenu

from ui.pages.playlists.dialogs import ask_name, confirm, edit_playlist


class PlaylistActions:
    """Dialogs and context menus that create / edit / delete playlists and fill them from song lists."""

    def __init__(self, parent, playlists, player, items, open_playlist_id):
        """items() -> [(Playlist, [Track])]; open_playlist_id() -> id of the playlist page on screen, or None."""
        self._parent, self._playlists, self._player = parent, playlists, player
        self._items, self._open_id = items, open_playlist_id

    def new_playlist(self, track_ids: list[int] | None = None):
        name = ask_name(self._parent, "New playlist", "Give your playlist a name.",
                        f"Playlist {len(self._items()) + 1}", "Create")
        if name:
            pid = self._playlists.create(name)
            if track_ids:
                self._playlists.add_tracks(pid, track_ids)

    def play(self, pid: int):
        for pl, tracks in self._items():
            if pl.id == pid and tracks:
                self._player.play_queue(tracks, 0)
                return

    def edit(self, pid: int):
        found = next(((pl, t) for pl, t in self._items() if pl.id == pid), None)
        if found is None:
            return
        res = edit_playlist(self._parent, *found)
        if res and res["name"]:
            self._playlists.update(pid, res["name"], res["description"], res["cover_src"], res["clear_cover"])

    def delete(self, pid: int):
        cur = next((pl.name for pl, _ in self._items() if pl.id == pid), "")
        if confirm(self._parent, "Delete playlist", f"“{cur}” will be deleted. The songs stay in your library.",
                   "Delete", danger=True):
            self._playlists.delete(pid)

    def song_menu(self, songs, model, pos):
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
        items = self._items()
        menu = QMenu(self._parent)
        sub = menu.addMenu("Add to playlist")
        for pl, _ in items:
            sub.addAction(pl.name, lambda checked=False, pid=pl.id: self._playlists.add_tracks(pid, ids))
        if items:
            sub.addSeparator()
        sub.addAction("New playlist…", lambda checked=False: self.new_playlist(ids))
        open_pid = self._open_id()
        if open_pid is not None:
            menu.addAction("Remove from this playlist",
                           lambda checked=False: self._playlists.remove_tracks(open_pid, ids))
        menu.exec(view.viewport().mapToGlobal(pos))
