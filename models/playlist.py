from dataclasses import dataclass


@dataclass(frozen=True)
class Playlist:
    id: int
    name: str
    created: float
    description: str = ""
    cover: str = ""  # path of a custom cover image; empty = automatic mosaic from the songs