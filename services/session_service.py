"""What is remembered between runs: volume, sort order, and the queue with the song and position it stopped at."""
from services.player_service import PlayerService


def ids_from_setting(raw) -> list[int]:
    """Track ids saved as "3,17,5" (a list is accepted too, in case a settings backend returns one)."""
    if raw is None:
        return []
    parts = raw if isinstance(raw, (list, tuple)) else str(raw).split(",")
    ids = []
    for x in parts:
        try:
            ids.append(int(x))
        except (TypeError, ValueError):
            pass
    return ids


class SessionService:
    def __init__(self, settings, player: PlayerService):
        self._s = settings
        self._player = player

    # --- simple values ---
    def volume(self) -> float:
        return float(self._s.value("volume", 0.75))

    def sort(self) -> str:
        return str(self._s.value("library/sort", "added"))

    def set_sort(self, key: str):
        self._s.setValue("library/sort", key)

    # --- queue ---
    def save(self):
        """Called on close: the queue as it is (an album, a playlist, a shuffled order ...), not the list on screen."""
        pl, st = self._player, self._s
        cur = pl.current
        if cur:
            st.setValue("last_track_id", cur.id)
            st.setValue("last_position", pl.position())
            st.setValue("queue/ids", ",".join(str(t.id) for t in pl.queue))
            st.setValue("queue/orig_ids", ",".join(str(t.id) for t in pl.orig_queue))
            st.setValue("queue/shuffle", pl.shuffle)
            st.setValue("queue/repeat", pl.repeat)
        st.setValue("volume", pl.volume())

    def restore(self, all_tracks: list, visible_tracks: list) -> int | None:
        """Bring the last queue back (paused). Returns the position in ms, or None if there was nothing to restore."""
        st = self._s
        try:
            tid = int(st.value("last_track_id"))
        except (TypeError, ValueError):
            return None
        if not all_tracks:
            return None
        by_id = {t.id: t for t in all_tracks}
        queue = [by_id[i] for i in ids_from_setting(st.value("queue/ids")) if i in by_id]
        index = next((i for i, t in enumerate(queue) if t.id == tid), -1)
        orig, shuffle, repeat = [], False, "off"
        if index >= 0:
            orig = [by_id[i] for i in ids_from_setting(st.value("queue/orig_ids")) if i in by_id]
            shuffle = str(st.value("queue/shuffle", False)).lower() in ("true", "1")
            repeat = str(st.value("queue/repeat", "off"))
        else:  # settings of an older version (no saved queue), or the song is gone: use the list on screen
            queue = visible_tracks
            index = next((i for i, t in enumerate(queue) if t.id == tid), -1)
            if index < 0:
                return None
        try:
            pos = int(st.value("last_position", 0))
        except (TypeError, ValueError):
            pos = 0
        self._player.restore(queue, index, pos, orig, shuffle, repeat)
        return pos
