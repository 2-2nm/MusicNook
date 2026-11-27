"""Drawing of a playlist cover: a custom image, or an automatic 2x2 mosaic of the songs' album covers."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

from ui.rendering.cover_renderer import CoverRenderer
from ui import theme
from ui.rendering.accent import pick_accent

_custom: dict[str, QPixmap] = {}


def custom_pixmap(path: str) -> QPixmap | None:
    if not path:
        return None
    px = _custom.get(path)
    if px is None:
        px = _custom[path] = QPixmap(path)
    return None if px.isNull() else px


MOSAIC_SCAN = 24  # songs looked at while searching for 4 different covers (each lookup reads a file's tags once)


def mosaic_tracks(tracks: list) -> list:
    """First song of up to 4 different covers (songs of one album can have a cover each)."""
    seen, out = set(), []
    for t in tracks[:MOSAIC_SCAN]:
        k = CoverRenderer.cover_key(t)
        if k not in seen:
            seen.add(k)
            out.append(t)
        if len(out) == 4:
            break
    return out


def draw_cover(p: QPainter, rect: QRectF, covers: list, custom: QPixmap | None, dpr: float):
    """Fills `rect` (square). The caller sets the rounded clip."""
    p.fillRect(rect, QColor("#12141f"))
    s = rect.width()
    if custom is not None:  # saved square by PlaylistService
        p.drawPixmap(rect, custom, QRectF(custom.rect()))
    elif len(covers) == 1:
        px = CoverRenderer.pixmap(covers[0], int(s * dpr), 0)
        p.drawPixmap(rect, px, QRectF(px.rect()))
    else:
        half = s / 2
        for i in range(4):
            r = QRectF(rect.x() + (i % 2) * half, rect.y() + (i // 2) * half, half, half).adjusted(1, 1, -1, -1)
            if i < len(covers):
                px = CoverRenderer.pixmap(covers[i], int(half * dpr), 0)
                p.drawPixmap(r, px, QRectF(px.rect()))
            else:
                p.fillRect(r, QColor("#070810"))


_tints: dict = {}


def playlist_tint(covers: list, custom: QPixmap | None, key=None) -> QColor | None:
    """Glow colour of a playlist: the dominant colour of its custom cover, or of the album covers in its mosaic
    (same picker as the player page). None when the playlist has no cover at all. `key` lets the result be reused
    while the same covers are shown."""
    ck = (key, tuple(t.id for t in covers), id(custom))
    if ck in _tints:
        return _tints[ck]
    pixmaps = [custom] if custom is not None else [CoverRenderer.pixmap(t, 48, 0) for t in covers]
    pixels = []
    for px in pixmaps:
        img = px.scaled(48, 48, Qt.IgnoreAspectRatio, Qt.SmoothTransformation).toImage().convertToFormat(QImage.Format_ARGB32)
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                if c.alpha() >= 128:
                    pixels.append((c.hsvHue(), c.hsvSaturationF(), c.valueF()))
    result = None
    if pixels:
        picked = pick_accent(pixels)
        if picked is None:  # grey / black artwork: the app's own accent, like on the player page
            result = QColor(theme.ACCENT)
        else:
            h, sat, val = picked
            result = QColor.fromHsvF(h / 360, min(0.95, max(sat, 0.55)), min(0.95, max(val, 0.75)))
    if len(_tints) > 64:
        _tints.clear()
    _tints[ck] = result
    return result