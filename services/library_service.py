import os
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from models.track import Track

try:
    import mutagen
except ImportError:  # pragma: no cover
    mutagen = None

AUDIO_EXT = {".mp3": "MP3", ".flac": "FLAC", ".m4a": "AAC", ".aac": "AAC",
             ".ogg": "OGG", ".opus": "OPUS", ".wav": "WAV", ".wma": "WMA"}


class LibraryService(QObject):
    changed = Signal()
    scanFinished = Signal(int)
    statsChanged = Signal()  # play counts / last played changed (cheap: no library reload)

    def __init__(self, parent=None):
        super().__init__(parent)
        base = Path(os.environ.get("APPDATA", Path.home())) / "AudioPlayer"
        base.mkdir(parents=True, exist_ok=True)
        self.db_path = str(base / "library.db")
        self._scanning = False
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS tracks(
                id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE,
                title TEXT, artist TEXT, album TEXT, added REAL, fmt TEXT, duration REAL)""")
            c.execute("""CREATE TABLE IF NOT EXISTS play_stats(
                track_id INTEGER PRIMARY KEY, play_count INTEGER NOT NULL DEFAULT 0, last_played REAL)""")

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def record_play(self, track_id: int):
        """One more play of this track (counted by the window once enough of it has been heard)."""
        with closing(self._conn()) as c:
            c.execute("""INSERT INTO play_stats(track_id, play_count, last_played) VALUES(?,1,?)
                         ON CONFLICT(track_id) DO UPDATE SET play_count=play_count+1, last_played=excluded.last_played""",
                      (track_id, time.time()))
            c.commit()
        self.statsChanged.emit()

    def play_stats(self) -> dict[int, tuple[int, float]]:
        """{track_id: (play_count, last_played)} for every track that has been played."""
        with closing(self._conn()) as c:
            rows = c.execute("SELECT track_id, play_count, last_played FROM play_stats").fetchall()
        return {r[0]: (r[1], r[2] or 0.0) for r in rows}

    def tracks(self) -> list[Track]:
        with self._conn() as c:
            rows = c.execute("SELECT id,path,title,artist,album,added,fmt,duration FROM tracks").fetchall()
        return [Track(*r) for r in rows if os.path.exists(r[1])]

    def scan(self, folder: str):
        if self._scanning:
            return
        self._scanning = True
        threading.Thread(target=self._scan, args=(folder,), daemon=True).start()

    def _scan(self, folder: str):
        added = 0
        try:
            conn = self._conn()
            known = {r[0] for r in conn.execute("SELECT path FROM tracks")}
            batch = 0
            for root, _, files in os.walk(folder):
                for name in files:
                    ext = os.path.splitext(name)[1].lower()
                    if ext not in AUDIO_EXT:
                        continue
                    path = os.path.join(root, name)
                    if path in known:
                        continue
                    title, artist, album, dur = Path(name).stem, "Unknown Artist", "Unknown Album", 0.0
                    if mutagen:
                        try:
                            f = mutagen.File(path, easy=True)
                            if f is not None:
                                tags = f.tags or {}
                                title = (tags.get("title") or [title])[0]
                                artist = (tags.get("artist") or [artist])[0]
                                album = (tags.get("album") or [album])[0]
                                dur = float(f.info.length or 0)
                        except Exception:
                            pass
                    conn.execute("INSERT OR IGNORE INTO tracks(path,title,artist,album,added,fmt,duration) VALUES(?,?,?,?,?,?,?)",
                                 (path, title, artist, album, os.path.getctime(path), AUDIO_EXT[ext], dur))
                    added += 1
                    batch += 1
                    if batch >= 100:
                        conn.commit()
                        batch = 0
                        self.changed.emit()
            conn.commit()
            conn.close()
        finally:
            self._scanning = False
            self.changed.emit()
            self.scanFinished.emit(added)
