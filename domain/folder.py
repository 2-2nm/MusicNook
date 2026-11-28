import os
from dataclasses import dataclass

KINDS = ("music", "lyrics")


@dataclass(frozen=True)
class Folder:
    id: int
    path: str
    kind: str          # "music" (the library is built from it) or "lyrics" (.lrc files are looked up in it)
    added: float = 0.0


def norm(path: str) -> str:
    """One spelling for a path (slashes, case on Windows) so C:/Music and C:\\music compare equal."""
    return os.path.normcase(os.path.normpath(path))


def is_under(path: str, folder: str) -> bool:
    p, f = norm(path), norm(folder)
    return p == f or p.startswith(f.rstrip(os.sep) + os.sep)


def count_under(paths, folders: list[str]) -> list[int]:
    """How many of `paths` lie inside each of `folders` (one pass over the paths)."""
    prefixes = [norm(f).rstrip(os.sep) + os.sep for f in folders]
    counts = [0] * len(prefixes)
    for path in paths:
        p = norm(path)
        for i, prefix in enumerate(prefixes):
            if p.startswith(prefix):
                counts[i] += 1
    return counts