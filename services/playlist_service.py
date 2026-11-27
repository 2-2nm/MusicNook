import os
import time
from contextlib import closing

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QImage

from data.db import Database
from domain.playlist import Playlist


class PlaylistService(QObject):
    """User playlists, stored in the same SQLite file as the library."""
    changed = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self._db = db
        self.covers_dir = db.covers_dir

    def _conn(self):
        return self._db.connect()

    def all(self) -> list[Playlist]:
        with closing(self._conn()) as c:
            rows = c.execute("SELECT id,name,created,COALESCE(description,''),COALESCE(cover,'') FROM playlists "
                             "ORDER BY created DESC, id DESC").fetchall()
        return [Playlist(*r) for r in rows]

    def track_ids(self, playlist_id: int) -> list[int]:
        with closing(self._conn()) as c:
            rows = c.execute("SELECT track_id FROM playlist_tracks WHERE playlist_id=? ORDER BY position",
                             (playlist_id,)).fetchall()
        return [r[0] for r in rows]

    def create(self, name: str) -> int:
        with closing(self._conn()) as c:
            cur = c.execute("INSERT INTO playlists(name,created) VALUES(?,?)", (name.strip(), time.time()))
            c.commit()
            pid = cur.lastrowid
        self.changed.emit()
        return pid

    @staticmethod
    def square_image(path: str, size: int = 600) -> QImage | None:
        """Any image, centre-cropped to a square and scaled to size x size. None if it cannot be read."""
        img = QImage(path)
        if img.isNull():
            return None
        side = min(img.width(), img.height())
        img = img.copy((img.width() - side) // 2, (img.height() - side) // 2, side, side)
        return img.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

    def update(self, playlist_id: int, name: str, description: str = "",
               cover_src: str | None = None, clear_cover: bool = False):
        """Edit name / description / cover. cover_src = a new image file to use, clear_cover = back to automatic."""
        with closing(self._conn()) as c:
            row = c.execute("SELECT cover FROM playlists WHERE id=?", (playlist_id,)).fetchone()
            old = row[0] if row else ""
            cover = old
            if cover_src:
                img = self.square_image(cover_src)
                if img is not None:
                    self.covers_dir.mkdir(parents=True, exist_ok=True)
                    dest = self.covers_dir / f"playlist_{playlist_id}_{int(time.time() * 1000)}.png"
                    if img.save(str(dest), "PNG"):
                        cover = str(dest)
            elif clear_cover:
                cover = ""
            c.execute("UPDATE playlists SET name=?, description=?, cover=? WHERE id=?",
                      (name.strip(), description.strip(), cover, playlist_id))
            c.commit()
        if old and cover != old:
            self._remove_file(old)
        self.changed.emit()

    @staticmethod
    def _remove_file(path: str):
        try:
            os.remove(path)
        except OSError:
            pass

    def delete(self, playlist_id: int):
        with closing(self._conn()) as c:
            row = c.execute("SELECT cover FROM playlists WHERE id=?", (playlist_id,)).fetchone()
            c.execute("DELETE FROM playlist_tracks WHERE playlist_id=?", (playlist_id,))
            c.execute("DELETE FROM playlists WHERE id=?", (playlist_id,))
            c.commit()
        if row and row[0]:
            self._remove_file(row[0])
        self.changed.emit()

    def remove_tracks(self, playlist_id: int, track_ids: list[int]):
        with closing(self._conn()) as c:
            c.executemany("DELETE FROM playlist_tracks WHERE playlist_id=? AND track_id=?",
                          [(playlist_id, t) for t in track_ids])
            c.commit()
        self.changed.emit()

    def add_tracks(self, playlist_id: int, track_ids: list[int]) -> int:
        """Append tracks that are not in the playlist yet. Returns how many were added."""
        added = 0
        with closing(self._conn()) as c:
            have = {r[0] for r in c.execute("SELECT track_id FROM playlist_tracks WHERE playlist_id=?", (playlist_id,))}
            pos = c.execute("SELECT COALESCE(MAX(position),-1) FROM playlist_tracks WHERE playlist_id=?",
                            (playlist_id,)).fetchone()[0]
            for tid in track_ids:
                if tid in have:
                    continue
                pos += 1
                c.execute("INSERT INTO playlist_tracks(playlist_id,track_id,position) VALUES(?,?,?)",
                          (playlist_id, tid, pos))
                have.add(tid)
                added += 1
            c.commit()
        if added:
            self.changed.emit()
        return added