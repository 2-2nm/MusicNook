"""App-wide names and locations. One place, so the settings key and the data folder can never drift apart.

"AudioPlayer" is the name the first versions shipped with; it stays so existing libraries / settings still load."""
import os
from pathlib import Path

APP_NAME = "MusicNook"
APP_USER_MODEL_ID = "MusicNook.Player"   # Windows taskbar grouping
LEGACY_NAME = "AudioPlayer"


def data_dir() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home())) / LEGACY_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def new_settings():
    from PySide6.QtCore import QSettings  # imported here so the data layer can run without Qt
    return QSettings(LEGACY_NAME, LEGACY_NAME)
