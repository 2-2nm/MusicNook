from datetime import datetime

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

BG = "#070810"
TEXT = "#f3f5ff"
MUTED = "#9aa0b8"
DIM = "#6b7190"
ACCENT = "#7c9cff"
GRAD_A = "#4f7bff"
GRAD_B = "#a77bff"


FAMILY = "Poppins"
FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def load_fonts() -> None:
    """Register the bundled fonts; call once after QApplication is created, before any widget."""
    for f in sorted(FONT_DIR.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(f))


def font(px: int, weight=QFont.Weight.Normal, spacing: float = 0.0) -> QFont:
    f = QFont()
    f.setFamilies([FAMILY, "Inter", "Segoe UI", "Arial"])
    f.setPixelSize(px)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


def fmt_time(ms: float) -> str:
    s = max(0, int(ms // 1000))
    return f"{s // 60}:{s % 60:02d}"


def fmt_added(ts: float) -> str:
    d = datetime.fromtimestamp(ts)
    return f"{d.day} {d:%b}"


STYLE = """
QToolTip{background:#14172a;color:#e8ebff;border:1px solid #2a2f4a;padding:4px 8px;}
QLabel{background:transparent;}
QPushButton#pill{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.10);border-radius:18px;padding:0 18px;color:#e8ebff;font-size:13px;}
QPushButton#pill:hover{background:rgba(255,255,255,0.10);}
QPushButton#pill:checked{background:rgba(124,156,255,0.25);border-color:rgba(124,156,255,0.5);}
QPushButton#pill::menu-indicator{image:none;width:0;}
QFrame#segFrame{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.10);border-radius:21px;}
QPushButton#seg{background:transparent;border:none;border-radius:17px;padding:0 20px;color:#aab0c8;font-size:15px;font-weight:600;}
QPushButton#seg:checked{background:rgba(255,255,255,0.14);color:#ffffff;}
QPushButton#seg:hover:!checked{color:#ffffff;}
QLineEdit#search{background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.10);border-radius:21px;padding:0 22px 0 46px;color:#f3f5ff;font-size:15px;selection-background-color:#4f7bff;}
QLineEdit#search:focus{border-color:rgba(124,156,255,0.6);}
QPushButton#primary{background:#ffffff;color:#0a0b14;border:none;border-radius:22px;padding:0 26px;font-size:15px;font-weight:600;}
QPushButton#primary:hover{background:#e6e9ff;}
QPushButton#secondary{background:rgba(255,255,255,0.12);color:#f3f5ff;border:none;border-radius:22px;padding:0 26px;font-size:15px;font-weight:600;}
QPushButton#secondary:hover{background:rgba(255,255,255,0.20);}
QListView{background:transparent;border:none;outline:none;}
QMenu{background:#12152a;border:1px solid #262b48;border-radius:10px;padding:6px;color:#e8ebff;}
QMenu::item{padding:7px 22px;border-radius:6px;}
QMenu::item:selected{background:rgba(124,156,255,0.25);}
"""