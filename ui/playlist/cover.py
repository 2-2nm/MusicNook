"""Drawing of a playlist cover: a custom image, or an automatic 2x2 mosaic of the songs' album covers."""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPixmap

from services.cover_service import CoverService

_custom: dict[str, QPixmap] = {}


def custom_pixmap(path: str) -> QPixmap | None:
    if not path:
        return None
    px = _custom.get(path)
    if px is None:
        px = _custom[path] = QPixmap(path)
    return None if px.isNull() else px


def mosaic_tracks(tracks: list) -> list:
    """First track of up to 4 different albums."""
    seen, out = set(), []
    for t in tracks:
        if t.album_key not in seen:
            seen.add(t.album_key)
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
        px = CoverService.pixmap(covers[0], int(s * dpr), 0)
        p.drawPixmap(rect, px, QRectF(px.rect()))
    else:
        half = s / 2
        for i in range(4):
            r = QRectF(rect.x() + (i % 2) * half, rect.y() + (i // 2) * half, half, half).adjusted(1, 1, -1, -1)
            if i < len(covers):
                px = CoverService.pixmap(covers[i], int(half * dpr), 0)
                p.drawPixmap(r, px, QRectF(px.rect()))
            else:
                p.fillRect(r, QColor("#070810"))