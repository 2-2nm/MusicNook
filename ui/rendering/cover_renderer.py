import hashlib
import zlib
from collections import OrderedDict

from PySide6.QtCore import QCoreApplication, QObject, QRectF, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPixmap

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


THUMB_MAX = 400  # longest side of the thumbnails kept in memory (enough for the album grid and the lists)

# Memory budgets. Every cache is a least-recently-used cache with a size limit in bytes: before, the thumbnails
# (up to 640 px each) and the full-size pictures of every album ever shown stayed in memory for good, and the
# rendered pixmaps were only dropped all at once after 1200 entries.
PIXMAP_BUDGET = 96 * 1024 * 1024   # rendered covers, one per (picture, size, radius)
THUMB_BUDGET = 40 * 1024 * 1024    # decoded thumbnails, the source for rendering a cover at a new size
IMAGE_BUDGET = 48 * 1024 * 1024    # full-size pictures (the big cover on the Player page)


class _Lru:
    """Dict with a size limit in bytes: the entry that was used longest ago goes first. The newest entry always stays."""

    def __init__(self, budget: int, sizeof):
        self._d: OrderedDict = OrderedDict()
        self._budget, self._sizeof = budget, sizeof
        self.bytes = 0

    def get(self, key):
        v = self._d.get(key)
        if v is not None:
            self._d.move_to_end(key)
        return v

    def __contains__(self, key):
        return key in self._d

    def put(self, key, value):
        old = self._d.pop(key, None)
        if old is not None:
            self.bytes -= self._sizeof(old)
        self._d[key] = value
        self.bytes += self._sizeof(value)
        while self.bytes > self._budget and len(self._d) > 1:
            _, dropped = self._d.popitem(last=False)
            self.bytes -= self._sizeof(dropped)

    def __len__(self):
        return len(self._d)


def _px_bytes(px: QPixmap) -> int:
    return px.width() * px.height() * 4


def _screen_scale() -> float:
    """Device pixel ratio of the screen: covers are drawn with that many pixels per point (1x screens need a quarter
    of the memory of the old fixed 2x)."""
    screen = QGuiApplication.primaryScreen()
    return max(1.0, screen.devicePixelRatio()) if screen else 1.0


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
    _images = _Lru(IMAGE_BUDGET, lambda i: i.sizeInBytes())     # hash -> full-size picture
    _thumbs = _Lru(THUMB_BUDGET, lambda i: i.sizeInBytes())     # hash -> thumbnail (<= THUMB_MAX)
    _pixmaps = _Lru(PIXMAP_BUDGET, _px_bytes)                   # (hash or album, size, radius) -> rendered cover
    _pending: set[str] = set()            # paths whose picture is being read right now
    _signals: _CoverSignals | None = None
    _pool: QThreadPool | None = None

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
    def stats(cls) -> str:
        """Memory held by the cover caches, for a quick look while tuning: print(CoverRenderer.stats())."""
        mb = lambda c: f"{c.bytes / 1048576:.0f} MB / {len(c)}"
        return f"pixmaps {mb(cls._pixmaps)} | thumbs {mb(cls._thumbs)} | full images {mb(cls._images)}"

    @classmethod
    def _finish(cls, path: str, digest, thumb):
        cls._pending.discard(path)
        if digest is not None and thumb is not None:
            if digest not in cls._thumbs:
                cls._thumbs.put(digest, thumb)
        else:
            digest = None
        cls._digest[path] = digest

    @classmethod
    def _store(cls, ck: tuple, make) -> QPixmap:
        px = cls._pixmaps.get(ck)
        if px is None:
            px = make()
            cls._pixmaps.put(ck, px)
        return px

    @classmethod
    def _album_cover(cls, track, size: int, radius: int) -> QPixmap:
        return cls._store(("album:" + track.album_key, size, radius),
                          lambda: cls._render(None, track.album_key, size, radius))

    @classmethod
    def pixmap_async(cls, track, size: int, radius: int) -> QPixmap:
        """Like pixmap(), but never reads a file on the calling thread. Until the picture of the song has been
        loaded in the background the album's generated cover is returned; signals().ready fires when it arrives."""
        sig = cls.signals()
        path = track.path
        digest = cls._digest.get(path, False)
        if digest is False:  # never looked at
            if path not in cls._pending:
                cls._pending.add(path)
                cls._pool.start(_CoverJob(path, sig))
            return cls._album_cover(track, size, radius)
        if digest is None:
            return cls._album_cover(track, size, radius)
        px = cls._pixmaps.get((digest, size, radius))
        if px is not None:
            return px
        img = cls._thumbs.get(digest)
        if img is None:
            img = cls._images.get(digest)
        if img is None:  # the thumbnail was pushed out of the cache: read it again in the background
            if path not in cls._pending:
                cls._pending.add(path)
                cls._pool.start(_CoverJob(path, sig))
            return cls._album_cover(track, size, radius)
        return cls._store((digest, size, radius), lambda: cls._render(img, track.album_key, size, radius))

    @classmethod
    def _load(cls, track, need: int = 0) -> tuple[str, QImage | None]:
        """(cache key, picture) of a song. `need` is the longest side (pixels) the caller wants to draw: a thumbnail
        is used when it is big enough, so the full picture is decoded only for big covers. Without an embedded
        picture the key is its album, so the generated placeholder looks the same for the whole album."""
        path = track.path
        digest = cls._digest.get(path, False)
        if digest is False:
            data = _embedded(path)
            digest = None
            if data:
                digest = hashlib.blake2b(data, digest_size=12).hexdigest()
                if digest not in cls._thumbs and digest not in cls._images:
                    img = QImage.fromData(data)
                    if img.isNull():
                        digest = None
                    else:
                        cls._remember(digest, img)
            cls._digest[path] = digest
        if digest is None:
            return "album:" + track.album_key, None
        thumb = cls._thumbs.get(digest)
        if thumb is not None:
            longest = max(thumb.width(), thumb.height())
            if need <= longest or longest < THUMB_MAX:  # big enough, or the picture is that small anyway
                return digest, thumb
        img = cls._images.get(digest)
        if img is None:  # only a thumbnail (or nothing) is known: decode the full picture
            data = _embedded(path)
            img = QImage.fromData(data) if data else QImage()
            if img.isNull():
                cls._digest[path] = None
                return "album:" + track.album_key, None
            cls._remember(digest, img)
        return digest, img

    @classmethod
    def _remember(cls, digest: str, img: QImage):
        """Keep a thumbnail of a freshly decoded picture; the full picture only when it is bigger than that."""
        if max(img.width(), img.height()) > THUMB_MAX:
            cls._images.put(digest, img)
            img = img.scaled(THUMB_MAX, THUMB_MAX, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        cls._thumbs.put(digest, img)

    @classmethod
    def cover_key(cls, track) -> str:
        """Same key = same picture (used to show different covers only once, e.g. in a playlist mosaic)."""
        return cls._load(track)[0]

    @classmethod
    def pixmap(cls, track, size: int, radius: int) -> QPixmap:
        digest = cls._digest.get(track.path, False)
        if digest:  # a cover already rendered at this size needs no picture at all
            px = cls._pixmaps.get((digest, size, radius))
            if px is not None:
                return px
        key, img = cls._load(track, int(size * _screen_scale()))
        return cls._store((key, size, radius), lambda: cls._render(img, track.album_key, size, radius))

    @classmethod
    def placeholder(cls, size: int, radius: int) -> QPixmap:
        return cls._store(("placeholder", size, radius), lambda: cls._render(None, "placeholder", size, radius))

    @staticmethod
    def _render(img, seed: str, size: int, radius: int) -> QPixmap:
        scale = _screen_scale()
        size = max(1, int(size))
        side = max(1, round(size * scale))
        px = QPixmap(side, side)
        px.setDevicePixelRatio(scale)
        px.fill(Qt.transparent)
        p = QPainter(px)
        try:
            p.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
            p.setClipPath(path)
            if img is not None:
                s = img.scaled(side, side, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                p.drawImage(QRectF(0, 0, size, size), s, QRectF((s.width() - side) / 2, (s.height() - side) / 2, side, side))
            else:
                c1, c2 = PALETTES[zlib.crc32(seed.encode()) % len(PALETTES)]
                g = QLinearGradient(0, 0, size, size)
                g.setColorAt(0, QColor(c1))
                g.setColorAt(1, QColor(c2))
                p.fillRect(QRectF(0, 0, size, size), g)
        finally:
            p.end()
        return px