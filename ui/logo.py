from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QTransform)

from ui import theme

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
RINGS_MIN_PX = 28  # below this size the vinyl rings would only turn into noise


def _note_path() -> QPainterPath:
    """Eighth note, drawn in a 100 x 100 box."""
    head = QPainterPath()
    head.addEllipse(QPointF(0, 0), 15.5, 11.5)
    head = QTransform().translate(39, 69).rotate(-22).map(head)

    stem = QPainterPath()
    stem.addRoundedRect(QRectF(50.5, 27, 6.5, 43), 3.2, 3.2)

    flag = QPainterPath()
    flag.moveTo(55, 27)
    flag.cubicTo(58, 41, 77, 43, 73, 62)
    flag.cubicTo(70, 54, 63, 51, 55, 50)
    flag.closeSubpath()

    return head.united(stem).united(flag)


def paint_logo(p: QPainter, rect: QRectF):
    """The MusicNook logo: a gradient squircle with a record and a music note."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(rect.topLeft())
    p.scale(rect.width() / 100, rect.height() / 100)

    shape = QPainterPath()
    shape.addRoundedRect(QRectF(0, 0, 100, 100), 30, 30)
    g = QLinearGradient(0, 0, 100, 100)
    g.setColorAt(0, QColor(theme.GRAD_A))
    g.setColorAt(1, QColor("#b46bff"))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawPath(shape)

    p.setClipPath(shape)
    if rect.width() >= RINGS_MIN_PX:  # faint record grooves behind the note
        p.setBrush(Qt.NoBrush)
        for r, a in ((46, 46), (36, 34), (26, 24)):
            p.setPen(QPen(QColor(255, 255, 255, a), 1.6))
            p.drawEllipse(QPointF(50, 50), r, r)
    gloss = QLinearGradient(0, 0, 0, 55)
    gloss.setColorAt(0, QColor(255, 255, 255, 46))
    gloss.setColorAt(1, QColor(255, 255, 255, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(gloss)
    p.drawRect(QRectF(0, 0, 100, 55))

    p.setBrush(QColor(0, 0, 0, 40))  # soft shadow under the note
    p.drawPath(QTransform().translate(0, 2.5).map(_note_path()))
    p.setBrush(QColor("#ffffff"))
    p.drawPath(_note_path())
    p.restore()


def logo_image(size: int) -> QImage:
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    paint_logo(p, QRectF(0, 0, size, size))
    p.end()
    return img


def app_icon() -> QIcon:
    """Window / taskbar icon, painted at every size so it stays sharp (no file needed)."""
    icon = QIcon()
    for s in ICON_SIZES:
        icon.addPixmap(QPixmap.fromImage(logo_image(s)))
    return icon
