import hashlib
import zlib

from PySide6.QtCore import QRectF, Qt
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


class CoverRenderer:
    """Covers are looked up per song: a song with its own embedded picture shows that picture, even when other
    songs of the same album have another one. Songs that carry the same picture (the usual case for an album)
    share one decoded image and one cache entry, found through a hash of the picture's bytes."""
    _digest: dict[str, str | None] = {}   # song path -> hash of its embedded picture (None: it has none)
    _images: dict[str, QImage] = {}       # hash -> decoded picture
    _pixmaps: dict[tuple, QPixmap] = {}

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
        return digest, cls._images[digest]

    @classmethod
    def cover_key(cls, track) -> str:
        """Same key = same picture (used to show different covers only once, e.g. in a playlist mosaic)."""
        return cls._load(track)[0]

    @classmethod
    def pixmap(cls, track, size: int, radius: int) -> QPixmap:
        key, img = cls._load(track)
        ck = (key, size, radius)
        if ck not in cls._pixmaps:
            cls._pixmaps[ck] = cls._render(img, track.album_key, size, radius)
        return cls._pixmaps[ck]

    @classmethod
    def placeholder(cls, size: int, radius: int) -> QPixmap:
        key = ("placeholder", size, radius)
        if key not in cls._pixmaps:
            cls._pixmaps[key] = cls._render(None, "placeholder", size, radius)
        return cls._pixmaps[key]

    @staticmethod
    def _render(img, seed: str, size: int, radius: int) -> QPixmap:
        scale = 2
        px = QPixmap(size * scale, size * scale)
        px.setDevicePixelRatio(scale)
        px.fill(Qt.transparent)
        p = QPainter(px)
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
        p.end()
        return px