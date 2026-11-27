from dataclasses import dataclass


@dataclass(frozen=True)
class Track:
    id: int
    path: str
    title: str
    artist: str
    album: str
    added: float
    fmt: str
    duration: float  # seconds
    year: int = 0    # release year, 0 = unknown
    genre: str = ""  # normalised genre name, "" = unknown

    @property
    def album_key(self) -> str:
        return f"{self.artist}|{self.album}"