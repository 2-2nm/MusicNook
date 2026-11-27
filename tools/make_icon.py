"""Writes assets/icon.png and assets/icon.ico (for PyInstaller's --icon, shortcuts, ...).
Run from the project root:  python tools/make_icon.py"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QGuiApplication

from ui.logo import ICON_SIZES, logo_image


def png_bytes(size: int) -> bytes:
    data = QByteArray()  # keep a reference: QBuffer does not own it
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    logo_image(size).save(buf, "PNG")
    buf.close()
    return bytes(data)


def main():
    app = QGuiApplication(sys.argv)  # noqa: F841 (needed by Qt for painting)
    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    (out / "icon.png").write_bytes(png_bytes(256))

    pngs = [(s, png_bytes(s)) for s in ICON_SIZES]
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, data = b"", b""
    for s, b in pngs:
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(b), offset + len(data))
        data += b
    (out / "icon.ico").write_bytes(head + entries + data)
    print("wrote", out / "icon.png", "and", out / "icon.ico")


if __name__ == "__main__":
    main()
