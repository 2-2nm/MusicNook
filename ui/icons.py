from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen


def draw_icon(p: QPainter, name: str, r: QRectF, color: str, filled_color: str | None = None):
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    c = QColor(color)
    pen = QPen(c, 1.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    s = min(r.width(), r.height())
    u = s / 24
    cx, cy = r.center().x(), r.center().y()

    def pt(a, b):
        return QPointF(cx + (a - 12) * u, cy + (b - 12) * u)

    def box(a, b, w, h):
        return QRectF(cx + (a - 12) * u, cy + (b - 12) * u, w * u, h * u)

    if name == "grid":
        for a, b in ((3.5, 3.5), (13.5, 3.5), (3.5, 13.5), (13.5, 13.5)):
            p.drawRoundedRect(box(a, b, 7, 7), 2 * u, 2 * u)
    elif name == "wave":
        for a, t, b in ((4, 10, 14), (8, 6, 18), (12, 3, 21), (16, 8, 16), (20, 10, 14)):
            p.drawLine(pt(a, t), pt(a, b))
    elif name == "queue":
        for y, x2 in ((6, 20), (12, 14), (18, 10)):
            p.drawLine(pt(4, y), pt(x2, y))
        p.drawLine(pt(17, 15), pt(21, 15))
        p.drawLine(pt(19, 13), pt(19, 17))
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(pt(3, 7))
        path.lineTo(pt(9, 7))
        path.lineTo(pt(11.5, 9.5))
        path.lineTo(pt(21, 9.5))
        path.lineTo(pt(21, 19))
        path.lineTo(pt(3, 19))
        path.closeSubpath()
        p.drawPath(path)
    elif name == "sun":
        p.drawEllipse(pt(12, 12), 4 * u, 4 * u)
        import math
        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(pt(12 + 7 * math.cos(a), 12 + 7 * math.sin(a)), pt(12 + 9.5 * math.cos(a), 12 + 9.5 * math.sin(a)))
    else:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(filled_color or color))
        if name == "play":
            path = QPainterPath()
            path.moveTo(pt(8, 5))
            path.lineTo(pt(19, 12))
            path.lineTo(pt(8, 19))
            path.closeSubpath()
            p.drawPath(path)
        elif name == "pause":
            p.drawRoundedRect(box(6.5, 5, 3.8, 14), 1.2 * u, 1.2 * u)
            p.drawRoundedRect(box(13.7, 5, 3.8, 14), 1.2 * u, 1.2 * u)
        elif name in ("prev", "next"):
            path = QPainterPath()
            if name == "prev":
                p.drawRoundedRect(box(5, 5.5, 2.6, 13), 1 * u, 1 * u)
                path.moveTo(pt(19, 5.5)); path.lineTo(pt(9.5, 12)); path.lineTo(pt(19, 18.5))
            else:
                p.drawRoundedRect(box(16.4, 5.5, 2.6, 13), 1 * u, 1 * u)
                path.moveTo(pt(5, 5.5)); path.lineTo(pt(14.5, 12)); path.lineTo(pt(5, 18.5))
            path.closeSubpath()
            p.drawPath(path)
    p.restore()
