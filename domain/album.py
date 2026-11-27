from dataclasses import dataclass


@dataclass(frozen=True)
class Album:
    """One album of the library: every track that shares the same artist and album tag."""
    key: str
    title: str
    artist: str
    year: int          # 0 = unknown
    tracks: tuple      # in album order
    added: float       # newest file of the album

    @property
    def duration(self) -> float:
        return sum(t.duration for t in self.tracks)

    @property
    def formats(self) -> list[str]:
        seen = []
        for t in self.tracks:
            if t.fmt and t.fmt not in seen:
                seen.append(t.fmt)
        return seen
