"""What goes into the smart collections and the "recent albums" row. No Qt widgets involved."""
import re
import time

from domain.album import Album
from domain.artist import Artist
from services.library_service import LibraryService

# Smart collections, in the order of the cards: Favourites, Recently played, Most played, Recently added
SMART_NAMES = ("Favourites", "Recently played", "Most played", "Recently added")
SMART_EMPTY = ("Favourites will show up here once you heart a song.",
               "Songs you listen to will show up here.",
               "Your most played songs will show up here.",
               "No songs in your library yet.")
PLAYLIST_EMPTY = "This playlist is empty. Right-click a song in your Library and choose Add to playlist."


def ago(ts: float, now: float | None = None) -> str:
    """Short "how long ago": 5 m ago, 3 h ago, 2 d ago ..."""
    s = max(0, int((now or time.time()) - ts))
    for unit, secs in (("y", 31536000), ("mo", 2592000), ("w", 604800), ("d", 86400), ("h", 3600), ("m", 60)):
        if s >= secs:
            return f"{s // secs} {unit} ago"
    return "just now"


class CollectionService:
    def __init__(self, library: LibraryService):
        self._library = library

    def smart_tracks(self, kind: int, all_tracks: list) -> list:
        by_id = {t.id: t for t in all_tracks}
        if kind == 3:  # newest files first
            return sorted(all_tracks, key=lambda t: t.added, reverse=True)[:30]
        if kind == 0:  # Favourites: needs the heart button (not built yet)
            return []
        stats = {i: s for i, s in self._library.play_stats().items() if i in by_id and s[0] > 0}
        if kind == 1:  # most recently played first
            ids = sorted(stats, key=lambda i: stats[i][1], reverse=True)
        else:          # most plays first, ties broken by the more recent one
            ids = sorted(stats, key=lambda i: (stats[i][0], stats[i][1]), reverse=True)
        return [by_id[i] for i in ids[:50]]

    def smart_extra(self, kind: int, tracks: list) -> tuple[str, dict[int, str]] | None:
        """The extra column of a smart collection: play counts for Most played, last played for Recently played."""
        if kind not in (1, 2):
            return None
        stats = self._library.play_stats()
        if kind == 2:
            return "PLAYS", {t.id: f"{stats[t.id][0]}\u00d7" for t in tracks if t.id in stats}
        return "PLAYED", {t.id: ago(stats[t.id][1]) for t in tracks if t.id in stats}

    @staticmethod
    def recent_albums(tracks: list) -> list:
        """The newest track of every album, newest first."""
        seen, recent = set(), []
        for t in sorted(tracks, key=lambda t: t.added, reverse=True):
            if t.album_key not in seen:
                seen.add(t.album_key)
                recent.append(t)
        return recent

    @staticmethod
    def albums(tracks: list) -> list[Album]:
        """Every album of the library, A-Z by title. Tracks keep file-name order (01 - ..., 02 - ...)."""
        def natural(t):
            return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", t.path.casefold())]
        groups: dict[str, list] = {}
        for t in tracks:
            groups.setdefault(t.album_key, []).append(t)
        out = []
        for key, ts in groups.items():
            ts.sort(key=natural)
            year = next((t.year for t in ts if t.year), 0)
            out.append(Album(key, ts[0].album, ts[0].artist, year, tuple(ts), max(t.added for t in ts)))
        out.sort(key=lambda a: (a.title.casefold(), a.artist.casefold()))
        return out

    @staticmethod
    def artists(albums: list) -> list[Artist]:
        """Every artist of the library, A-Z. Albums newest year first (unknown year last)."""
        groups: dict[str, list] = {}
        for a in albums:
            groups.setdefault((a.artist or "").strip().casefold(), []).append(a)
        out = []
        for key, als in groups.items():
            als.sort(key=lambda a: (a.year == 0, -a.year, a.title.casefold()))
            name = (als[0].artist or "").strip() or "Unknown artist"
            out.append(Artist(key, name, tuple(als), tuple(t for a in als for t in a.tracks)))
        out.sort(key=lambda a: a.name.casefold())
        return out

    @staticmethod
    def stats_text(tracks: list) -> str:
        total = sum(t.duration for t in tracks)
        h, m = int(total // 3600), int(total % 3600 // 60)
        return (f"{len(tracks)} song" + ("" if len(tracks) == 1 else "s")
                + (f" · {h} h {m} m" if tracks else ""))
