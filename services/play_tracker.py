from services.library_service import LibraryService
from services.player_service import PlayerService


class PlayTracker:
    """A play counts once it is actually playing and has reached 30 s (or half of a short track)."""

    def __init__(self, player: PlayerService, library: LibraryService):
        self._player = player
        self._library = library
        self._counted_id = None

    def reset(self):
        self._counted_id = None

    def update(self, cur, pos: int, dur: int):
        if cur is None or self._counted_id == cur.id or not self._player.is_playing():
            return
        if pos >= (min(30000, dur // 2) if dur else 30000):
            self._counted_id = cur.id
            self._library.record_play(cur.id)
