from dataclasses import dataclass


@dataclass(frozen=True)
class Artist:
    """One artist of the library: every album that shares the same artist tag."""
    key: str
    name: str
    albums: tuple   # newest year first
    tracks: tuple   # album by album, in album order

    @property
    def duration(self) -> float:
        return sum(t.duration for t in self.tracks)

    def popular(self, stats: dict, n: int = 6) -> list:
        """Most played songs first (stats = {track_id: (play_count, last_played)}); the rest keep library order."""
        count = lambda t: stats.get(t.id, (0, 0.0))[0]
        played = sorted((t for t in self.tracks if count(t) > 0), key=count, reverse=True)
        seen = {t.id for t in played}
        return (played + [t for t in self.tracks if t.id not in seen])[:n]
