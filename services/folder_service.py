import os
import time
from contextlib import closing

from PySide6.QtCore import QObject, Signal

from data.db import Database
from domain.folder import KINDS, Folder, is_under, norm


class FolderService(QObject):
    """The folders the user added: music folders (the library) and lyrics folders (.lrc files)."""
    changed = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self._db = db

    def items(self, kind: str | None = None) -> list[Folder]:
        sql = "SELECT id, path, kind, COALESCE(added, 0) FROM folders"
        args: tuple = ()
        if kind:
            sql += " WHERE kind=?"
            args = (kind,)
        with closing(self._db.connect()) as c:
            rows = c.execute(sql + " ORDER BY id", args).fetchall()
        return [Folder(*r) for r in rows]

    def add(self, path: str, kind: str) -> str | None:
        """Adds a folder. Returns None when it was added, otherwise a message that says why not."""
        if kind not in KINDS:
            return "Unknown folder type."
        path = os.path.normpath(path)
        if not os.path.isdir(path):
            return "That folder does not exist."
        for f in self.items(kind):
            if norm(f.path) == norm(path):
                return "This folder is already in the list."
            if is_under(path, f.path):
                return f"It is already covered by {f.path}."
        with closing(self._db.connect()) as c:
            c.execute("INSERT OR IGNORE INTO folders(path, kind, added) VALUES(?,?,?)", (path, kind, time.time()))
            c.commit()
        self.changed.emit()
        return None

    def remove(self, folder_id: int):
        with closing(self._db.connect()) as c:
            c.execute("DELETE FROM folders WHERE id=?", (folder_id,))
            c.commit()
        self.changed.emit()