import hashlib
import zlib

from PySide6.QtCore import QCoreApplication, QObject, QRectF, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPixmap

try:
    import mutagen
except ImportError:  # pragma: no cover
    mutagen = None

PALETTES = [("#0f3d33", "#d6f28b"), ("#4a1230", "#f5a58f"), ("#1c1a4d", "#9a74ff"),
            ("#4a2c06", "#f5b95a"), ("#2a2d33", "#e6e8ee"), ("#0b2a3a", "#4cc3d9"),
            ("#3b0f3f", "#ff7ab8"), ("#173a1a", "#7be28f")]


def _embedded(path: str) -> bytes | None:
    if not mutagen:
        return None
    try:
        f = mutagen.File(path)
        if f is None:
            return None
        if getattr(f, "pictures", None):
            return f.pictures[0].data
        tags = f.tags
        if tags is None:
            return None
        for k in tags.keys():
            if str(k).startswith("APIC"):
                return tags[k].data
        if "covr" in tags:
            return bytes(tags["covr"][0])
    except Exception:
        return None
    return None


THUMB_MAX = 640  # longest side of the thumbnails the album grid uses (keeps memory small)


class _CoverSignals(QObject):
    """Lives in the GUI thread. The worker threads emit `loaded`; the queued connection makes the slot run here."""
    loaded = Signal(str, object, object)  # path, digest (None: no picture), thumbnail QImage (or None)
    ready = Signal()                      # some cover became available: repaint

    def __init__(self):
        super().__init__()
        self.loaded.connect(self._on_loaded, Qt.QueuedConnection)

    @Slot(str, object, object)
    def _on_loaded(self, path, digest, img):
        CoverRenderer._finish(path, digest, img)
        self.ready.emit()


class _CoverJob(QRunnable):
    """Reads and decodes the embedded picture of one file off the GUI thread."""

    def __init__(self, path: str, signals: _CoverSignals):
        super().__init__()
        self._path, self._signals = path, signals

    def run(self):
        digest, thumb = None, None
        try:
            data = _embedded(self._path)
            if data:
                img = QImage.fromData(data)
                if not img.isNull():
                    digest = hashlib.blake2b(data, digest_size=12).hexdigest()
                    if max(img.width(), img.height()) > THUMB_MAX:
                        img = img.scaled(THUMB_MAX, THUMB_MAX, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    thumb = img
        except Exception:
            digest, thumb = None, None
        try:
            self._signals.loaded.emit(self._path, digest, thumb)
        except RuntimeError:  # the application is shutting down
            pass


class CoverRenderer:
    """Covers are looked up per song: a song with its own embedded picture shows that picture, even when other
    songs of the same album have another one. Songs that carry the same picture (the usual case for an album)
    share one decoded image and one cache entry, found through a hash of the picture's bytes."""
    _digest: dict[str, str | None] = {}   # song path -> hash of its embedded picture (None: it has none)
    _images: dict[str, QImage] = {}       # hash -> decoded picture
    _pixmaps: dict[tuple, QPixmap] = {}
    _thumbs: dict[str, QImage] = {}       # hash -> small picture decoded in the background (album grid)
    _pending: set[str] = set()            # paths whose picture is being read right now
    _signals: _CoverSignals | None = None
    _pool: QThreadPool | None = None
    _MAX_PIXMAPS = 1200

    @classmethod
    def signals(cls) -> _CoverSignals:
        """GUI-thread only. `signals().ready` fires whenever a background-loaded cover arrives."""
        if cls._signals is None:
            cls._signals = _CoverSignals()
            cls._pool = QThreadPool()
            cls._pool.setMaxThreadCount(2)
            app = QCoreApplication.instance()
            if app is not None:
                app.aboutToQuit.connect(cls._pool.clear)
        return cls._signals

    @classmethod
    def _finish(cls, path: str, digest, thumb):
        cls._pending.discard(path)
        if digest is not None and thumb is not None:
            cls._thumbs.setdefault(digest, thumb)
        else:
            digest = None
        cls._digest[path] = digest

    @classmethod
    def _store(cls, ck: tuple, make) -> QPixmap:
        if len(cls._pixmaps) > cls._MAX_PIXMAPS:  # a window resize makes every size new: do not grow forever
            cls._pixmaps.clear()
        if ck not in cls._pixmaps:
            cls._pixmaps[ck] = make()
        return cls._pixmaps[ck]

    @classmethod
    def pixmap_async(cls, track, size: int, radius: int) -> QPixmap:
        """Like pixmap(), but never reads a file on the calling thread. Until the picture of the song has been
        loaded in the background the album's generated cover is returned; signals().ready fires when it arrives."""
        sig = cls.signals()
        path = track.path
        if path not in cls._digest:
            if path not in cls._pending:
                cls._pending.add(path)
                cls._pool.start(_CoverJob(path, sig))
            return cls._store(("album:" + track.album_key, size, radius),
                              lambda: cls._render(None, track.album_key, size, radius))
        digest = cls._digest[path]
        if digest is None:
            return cls._store(("album:" + track.album_key, size, radius),
                              lambda: cls._render(None, track.album_key, size, radius))
        img = cls._images.get(digest)
        if img is None:
            img = cls._thumbs.get(digest)
        return cls._store((digest, size, radius), lambda: cls._render(img, track.album_key, size, radius))

    @classmethod
    def _load(cls, track) -> tuple[str, QImage | None]:
        """(cache key, picture) of a song. Without an embedded picture the key is its album, so the generated
        placeholder looks the same for the whole album."""
        path = track.path
        if path not in cls._digest:
            data = _embedded(path)
            digest = None
            if data:
                digest = hashlib.blake2b(data, digest_size=12).hexdigest()
                if digest not in cls._images:
                    img = QImage.fromData(data)
                    if img.isNull():
                        digest = None
                    else:
                        cls._images[digest] = img
            cls._digest[path] = digest
        digest = cls._digest[path]
        if digest is None:
            return "album:" + track.album_key, None
        if digest not in cls._images:  # only a thumbnail is known so far: decode the full picture
            data = _embedded(path)
            img = QImage.fromData(data) if data else QImage()
            if img.isNull():
                cls._digest[path] = None
                return "album:" + track.album_key, None
            cls._images[digest] = img
        return digest, cls._images[digest]

    @classmethod
    def cover_key(cls, track) -> str:
        """Same key = same picture (used to show different covers only once, e.g. in a playlist mosaic)."""
        return cls._load(track)[0]

    @classmethod
    def pixmap(cls, track, size: int, radius: int) -> QPixmap:
        key, img = cls._load(track)
        return cls._store((key, size, radius), lambda: cls._render(img, track.album_key, size, radius))

    @classmethod
    def placeholder(cls, size: int, radius: int) -> QPixmap:
        key = ("placeholder", size, radius)
        if key not in cls._pixmaps:
            cls._pixmaps[key] = cls._render(None, "placeholder", size, radius)
        return cls._pixmaps[key]

    @staticmethod
    def _render(img, seed: str, size: int, radius: int) -> QPixmap:
        scale = 2
        size = max(1, int(size))
        px = QPixmap(size * scale, size * scale)
        px.setDevicePixelRatio(scale)
        px.fill(Qt.transparent)
        p = QPainter(px)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
            p.setClipPath(path)
            if img is not None:
                s = img.scaled(size * scale, size * scale, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                p.drawImage(QRectF(0, 0, size, size), s, QRectF((s.width() - size * scale) / 2, (s.height() - size * scale) / 2, size * scale, size * scale))
            else:
                c1, c2 = PALETTES[zlib.crc32(seed.encode()) % len(PALETTES)]
                g = QLinearGradient(0, 0, size, size)
                g.setColorAt(0, QColor(c1))
                g.setColorAt(1, QColor(c2))
                p.fillRect(QRectF(0, 0, size, size), g)
        finally:
            p.end()
        return px