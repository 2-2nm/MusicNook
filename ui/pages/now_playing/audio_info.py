"""Helpers that read extra info for a track: audio quality text and synced (.lrc) lyrics."""
import re
from pathlib import Path

try:
    import mutagen
except ImportError:  # pragma: no cover
    mutagen = None

_quality_cache: dict[str, str] = {}
_STAMP = re.compile(r"\[(\d+):(\d+(?:[.:]\d+)?)\]")


def quality(track) -> str:
    """e.g. 'FLAC · 24-bit / 96 kHz' or 'MP3 · 320 kbps'. Falls back to the plain format name."""
    if track.path in _quality_cache:
        return _quality_cache[track.path]
    fmt = (track.fmt or "").upper()
    parts: list[str] = []
    if mutagen:
        try:
            info = getattr(mutagen.File(track.path), "info", None)
            if info is not None:
                bits = getattr(info, "bits_per_sample", 0) or 0
                rate = getattr(info, "sample_rate", 0) or 0
                kbps = getattr(info, "bitrate", 0) or 0
                if bits and rate:
                    parts.append(f"{bits}-bit / {rate / 1000:g} kHz")
                elif kbps:
                    parts.append(f"{round(kbps / 1000)} kbps")
                elif rate:
                    parts.append(f"{rate / 1000:g} kHz")
        except Exception:
            pass
    text = " · ".join([p for p in [fmt] + parts if p])
    _quality_cache[track.path] = text
    return text


def load_lyrics(path: str) -> list[tuple[int, str]]:
    """Synced lyrics from a .lrc file with the same name next to the song. Returns [(ms, text)]."""
    p = Path(path).with_suffix(".lrc")
    if not p.is_file():
        return []
    try:
        raw = p.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raw = p.read_text(encoding="latin-1")
    except OSError:
        return []
    lines: list[tuple[int, str]] = []
    for row in raw.splitlines():
        stamps = _STAMP.findall(row)
        if not stamps:
            continue
        text = _STAMP.sub("", row).strip() or "♪"
        for minutes, seconds in stamps:
            ms = int((int(minutes) * 60 + float(seconds.replace(":", "."))) * 1000)
            lines.append((ms, text))
    lines.sort(key=lambda x: x[0])
    return lines
