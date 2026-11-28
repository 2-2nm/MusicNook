import os
import re
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal, Slot

from services.folder_service import FolderService

_SPACES = re.compile(r"\s+")


def _key(name: str) -> str:
    return _SPACES.sub(" ", name).strip().casefold()


class LyricsFinder(QObject):
    """Finds the .lrc file of a song: next to the song first, then in the lyrics folders.

    In the lyrics folders a file matches when its name is the song's file name, "Artist - Title" or the title
    (all without the extension, case does not matter). The folders are indexed in a background thread."""
    indexChanged = Signal()
    _built = Signal(int, object, object)

    def __init__(self, folders: FolderService, parent=None):
        super().__init__(parent)
        self._folders = folders
        self._index: dict[str, str] = {}
        self._counts: dict[int, int] = {}
        self._gen = 0
        self._built.connect(self._on_built, Qt.QueuedConnection)
        folders.changed.connect(self.rebuild)
        self.rebuild()

    def counts(self) -> dict[int, int]:
        """{lyrics folder id: number of .lrc files found in it}"""
        return self._counts

    def rebuild(self):
        self._gen += 1
        folders = [(f.id, f.path) for f in self._folders.items("lyrics")]
        threading.Thread(target=self._work, args=(self._gen, folders), daemon=True).start()

    def _work(self, gen: int, folders: list):
        index: dict[str, str] = {}
        counts: dict[int, int] = {}
        try:
            for fid, path in folders:
                n = 0
                for root, _, files in os.walk(path):
                    for name in files:
                        if name.lower().endswith(".lrc"):
                            n += 1
                            index.setdefault(_key(Path(name).stem), os.path.join(root, name))
                counts[fid] = n
        except Exception:
            pass
        try:
            self._built.emit(gen, index, counts)
        except RuntimeError:  # shutting down
            pass

    @Slot(int, object, object)
    def _on_built(self, gen: int, index, counts):
        if gen != self._gen:  # a newer rebuild is on its way
            return
        self._index, self._counts = index, counts
        self.indexChanged.emit()

    def find(self, audio_path: str, title: str = "", artist: str = "") -> str | None:
        own = Path(audio_path).with_suffix(".lrc")
        if own.is_file():
            return str(own)
        index = self._index
        if not index:
            return None
        keys = [_key(Path(audio_path).stem)]
        if artist and title:
            keys.append(_key(f"{artist} - {title}"))
        if title:
            keys.append(_key(title))
        for k in keys:
            if k and k in index:
                return index[k]
        return None