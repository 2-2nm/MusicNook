import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QImage

from models.playlist import Playlist


class PlaylistService(QObject):
    """User playlists, stored in the same SQLite file as the library."""
    changed = Signal()

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.covers_dir = Path(db_path).parent / "covers"
        with closing(self._conn()) as c:
            c.execute("""CREATE TABLE IF NOT EXISTS playlists(
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created REAL)""")
            cols = {r[1] for r in c.execute("PRAGMA table_info(playlists)")}  # upgrade older databases
            if "description" not in cols:
                c.execute("ALTER TABLE playlists ADD COLUMN description TEXT NOT NULL DEFAULT ''")
            if "cover" not in cols:
                c.execute("ALTER TABLE playlists ADD COLUMN cover TEXT NOT NULL DEFAULT ''")
            c.execute("""CREATE TABLE IF NOT EXISTS playlist_tracks(
                playlist_id INTEGER, track_id INTEGER, position INTEGER,
                PRIMARY KEY(playlist_id, track_id))""")
            c.commit()

    def _conn(self):
        return sqlite3.connect(self.db_path)

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