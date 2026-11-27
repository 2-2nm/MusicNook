from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal

from domain.track import Track


class TrackListModel(QAbstractListModel):
    TrackRole = Qt.UserRole + 1
    ExtraRole = Qt.UserRole + 2   # text of the optional extra column (play count ...), "" if none
    extraChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.extra_title = ""            # header of the extra column; "" = no extra column
        self._extra: dict[int, str] = {}  # track id -> text
        self._all: list[Track] = []
        self._rows: list[Track] = []
        self.sort_key = "added"
        self._query = ""
        self._formats: set[str] = set()

    # --- Qt API ---
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        t = self._rows[index.row()]
        if role == self.TrackRole:
            return t
        if role == self.ExtraRole:
            return self._extra.get(t.id, "")
        if role == Qt.DisplayRole:
            return t.title
        return None

    # --- data ---
    def set_tracks(self, tracks: list[Track]):
        self._all = list(tracks)
        self._refresh()

    def set_extra(self, title: str = "", values: dict[int, str] | None = None):
        """Optional column shown just before TIME (e.g. \"PLAYS\" with {track_id: \"42\u00d7\"}). Call before set_tracks."""
        self.extra_title = title
        self._extra = dict(values or {})
        self.extraChanged.emit()

    def set_sort(self, key: str):
        self.sort_key = key
        self._refresh()

    def set_query(self, q: str):
        self._query = q.strip().casefold()
        self._refresh()

    def set_formats(self, formats: set[str]):
        self._formats = set(formats)
        self._refresh()

    @property
    def formats(self) -> set[str]:
        return self._formats

    def available_formats(self) -> list[str]:
        return sorted({t.fmt for t in self._all})

    def visible_tracks(self) -> list[Track]:
        return list(self._rows)

    def track_at(self, row: int) -> Track | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    def first_row_for_letter(self, letter: str) -> int:
        for i, t in enumerate(self._rows):
            c = t.title[:1].upper()
            if (letter == "#" and not c.isalpha()) or c == letter:
                return i
        return -1

    def _refresh(self):
        rows = self._all
        if self._formats:
            rows = [t for t in rows if t.fmt in self._formats]
        if self._query:
            q = self._query
            rows = [t for t in rows if q in t.title.casefold() or q in t.artist.casefold() or q in t.album.casefold() or q in t.genre.casefold()]
        key = self.sort_key
        if key == "manual":
            pass  # keep the order the list was given in (playlist order, most played ...)
        elif key == "added":
            rows = sorted(rows, key=lambda t: t.added, reverse=True)
        elif key == "year":
            # newest release first; tracks without a year always go last
            known = sorted((t for t in rows if t.year), key=lambda t: (-t.year, t.album.casefold(), t.title.casefold()))
            rows = known + sorted((t for t in rows if not t.year), key=lambda t: t.title.casefold())
        elif key == "genre":
            known = sorted((t for t in rows if t.genre), key=lambda t: (t.genre.casefold(), t.artist.casefold(), t.title.casefold()))
            rows = known + sorted((t for t in rows if not t.genre), key=lambda t: t.title.casefold())
        else:
            rows = sorted(rows, key=lambda t: (getattr(t, key).casefold(), t.title.casefold()))
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()