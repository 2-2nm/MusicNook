import os
import re
import threading
import time
from contextlib import closing
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from data.db import Database
from domain.track import Track

try:
    import mutagen
except ImportError:  # pragma: no cover
    mutagen = None

try:
    from mutagen.id3 import GENRES as _ID3_GENRES
except Exception:  # pragma: no cover
    _ID3_GENRES = []

_YEAR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
_GENRE_NUM_RE = re.compile(r"^\(?(\d{1,3})\)?$")
_GENRE_PREFIX_RE = re.compile(r"^\((\d{1,3})\)\s*(.*)$")


def parse_year(tags) -> int:
    """Release year from whatever date tag is present (2021, 2021-05, 2021-05-03 ...). 0 = unknown."""
    for key in ("originaldate", "date", "year"):
        for v in (tags.get(key) or []):
            m = _YEAR_RE.search(str(v))
            if m and 1000 <= int(m.group(1)) <= 2999:
                return int(m.group(1))
    return 0


def _genre_name(raw: str) -> str:
    raw = raw.strip()
    m = _GENRE_PREFIX_RE.match(raw)  # "(17)Rock" or "(17)"
    if m:
        raw = m.group(2).strip() or m.group(1)
    m = _GENRE_NUM_RE.match(raw)  # old ID3v1 style number: "17"
    if m:
        n = int(m.group(1))
        return _ID3_GENRES[n] if n < len(_ID3_GENRES) else ""
    return raw


def parse_genre(tags) -> str:
    """Genre names with old ID3v1 numbers resolved; several genres are joined with a comma."""
    names = []
    for v in (tags.get("genre") or []):
        for part in str(v).replace("\x00", "/").split("/"):
            n = _genre_name(part)
            if n and n not in names:
                names.append(n)
    return ", ".join(names)


def read_meta(path: str, title: str, artist: str, album: str):
    """(title, artist, album, duration, year, genre) for one file; falls back to the given defaults."""
    dur, year, genre = 0.0, 0, ""
    if mutagen:
        try:
            f = mutagen.File(path, easy=True)
            if f is not None:
                tags = f.tags or {}
                title = (tags.get("title") or [title])[0]
                artist = (tags.get("artist") or [artist])[0]
                album = (tags.get("album") or [album])[0]
                dur = float(f.info.length or 0)
                year = parse_year(tags)
                genre = parse_genre(tags)
        except Exception:
            pass
    return title, artist, album, dur, year, genre

AUDIO_EXT = {".mp3": "MP3", ".flac": "FLAC", ".m4a": "AAC", ".aac": "AAC",
             ".ogg": "OGG", ".opus": "OPUS", ".wav": "WAV", ".wma": "WMA"}


class LibraryService(QObject):
    changed = Signal()
    scanFinished = Signal(int)
    statsChanged = Signal()  # play counts / last played changed (cheap: no library reload)

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self._db = db
        self._scanning = False
        QTimer.singleShot(300, self._start_backfill)  # tracks added before year/genre existed

    def _conn(self):
        return self._db.connect()

    def _start_backfill(self):
        threading.Thread(target=self._backfill, daemon=True).start()

    def _backfill(self):
        """Read year / genre once for tracks that predate those columns. Only the tags are re-read."""
        try:
            with closing(self._conn()) as c:
                todo = c.execute("SELECT id, path FROM tracks WHERE year IS NULL").fetchall()
                n = 0
                for tid, path in todo:
                    if not os.path.exists(path):
                        continue
                    *_, year, genre = read_meta(path, "", "", "")
                    c.execute("UPDATE tracks SET year=?, genre=? WHERE id=?", (year, genre, tid))
                    n += 1
                    if n % 100 == 0:
                        c.commit()
                        self.changed.emit()
                c.commit()
            if todo:
                self.changed.emit()
        except Exception:
            pass

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
            rows = c.execute("SELECT id,path,title,artist,album,added,fmt,duration,"
                            "COALESCE(year,0),COALESCE(genre,'') FROM tracks").fetchall()
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
                    title, artist, album, dur, year, genre = read_meta(path, Path(name).stem, "Unknown Artist", "Unknown Album")
                    conn.execute("INSERT OR IGNORE INTO tracks(path,title,artist,album,added,fmt,duration,year,genre) VALUES(?,?,?,?,?,?,?,?,?)",
                                 (path, title, artist, album, os.path.getctime(path), AUDIO_EXT[ext], dur, year, genre))
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