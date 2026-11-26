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


class CoverService:
    _images: dict[str, QImage | None] = {}
    _pixmaps: dict[tuple, QPixmap] = {}

    @classmethod
    def pixmap(cls, track, size: int, radius: int) -> QPixmap:
        key = (track.album_key, size, radius)
        if key in cls._pixmaps:
            return cls._pixmaps[key]
        if track.album_key not in cls._images:
            data = _embedded(track.path)
            img = QImage.fromData(data) if data else None
            cls._images[track.album_key] = img if img is not None and not img.isNull() else None
        px = cls._render(cls._images[track.album_key], track.album_key, size, radius)
        cls._pixmaps[key] = px
        return px

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
