import random

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from domain.track import Track


class PlayerService(QObject):
    trackChanged = Signal(object)
    positionChanged = Signal(int)
    durationChanged = Signal(int)
    playingChanged = Signal(bool)
    volumeChanged = Signal(float)
    modesChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._queue: list[Track] = []
        self._index = -1
        self._pending_seek: int | None = None
        self._shuffle = False
        self._repeat = "off"  # off | all | one
        self._orig: list[Track] = []  # queue order before shuffling
        self._player.positionChanged.connect(lambda v: self.positionChanged.emit(int(v)))
        self._player.durationChanged.connect(lambda v: self.durationChanged.emit(int(v)))
        self._player.playbackStateChanged.connect(
            lambda s: self.playingChanged.emit(s == QMediaPlayer.PlaybackState.PlayingState))
        self._player.mediaStatusChanged.connect(self._on_status)

    # --- state ---
    @property
    def current(self) -> Track | None:
        return self._queue[self._index] if 0 <= self._index < len(self._queue) else None

    @property
    def queue(self) -> list[Track]:
        return self._queue

    @property
    def index(self) -> int:
        return self._index

    @property
    def orig_queue(self) -> list[Track]:
        """The queue in its order before shuffling (empty while shuffle is off)."""
        return self._orig

    @property
    def shuffle(self) -> bool:
        return self._shuffle

    @property
    def repeat(self) -> str:
        return self._repeat

    def position(self) -> int:
        return self._player.position()

    def duration(self) -> int:
        return self._player.duration()

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    # --- control ---
    def play_queue(self, tracks: list[Track], index: int = 0):
        self._orig = []
        self._queue = list(tracks)
        if self._shuffle and 0 <= index < len(self._queue):
            self._orig = list(self._queue)
            picked = self._queue.pop(index)
            random.shuffle(self._queue)
            self._queue.insert(0, picked)
            index = 0
        self._load(index, autoplay=True)

    def enqueue(self, tracks: list[Track]):
        """Add songs to the end of the queue (starts playing them when nothing is queued)."""
        if not tracks:
            return
        if not self._queue or self._index < 0:
            self.play_queue(tracks, 0)
            return
        self._queue.extend(tracks)
        if self._orig:
            self._orig.extend(tracks)

    def play_index(self, index: int):
        """Jump to a position of the current queue without touching its order."""
        self._load(index, autoplay=True)

    def shuffle_all(self, tracks: list[Track]):
        q = list(tracks)
        random.shuffle(q)
        if q:
            self.play_queue(q, 0)

    def restore(self, tracks: list[Track], index: int, position_ms: int,
                orig: list[Track] | None = None, shuffle: bool = False, repeat: str = "off"):
        """Bring back the queue of the last session (same order, shuffle and repeat), paused at `position_ms`."""
        self._queue = list(tracks)
        self._orig = list(orig) if (shuffle and orig) else []
        self._shuffle = shuffle and bool(self._orig)  # shuffle without its original order could not be undone
        self._repeat = repeat if repeat in ("off", "all", "one") else "off"
        self._load(index, autoplay=False, seek=position_ms)
        self.modesChanged.emit()

    def _load(self, index: int, autoplay: bool, seek: int = 0):
        if not (0 <= index < len(self._queue)):
            return
        self._index = index
        self._pending_seek = seek or None
        self._player.setSource(QUrl.fromLocalFile(self.current.path))
        self.trackChanged.emit(self.current)
        if autoplay:
            self._player.play()

    def play(self):
        if self.current:
            self._player.play()

    def pause(self):
        self._player.pause()

    def toggle(self):
        self.pause() if self.is_playing() else self.play()

    def next(self):
        if self._index + 1 < len(self._queue):
            self._load(self._index + 1, autoplay=True)
        elif self._repeat == "all" and self._queue:
            self._load(0, autoplay=True)
        else:
            self._player.stop()

    def prev(self):
        if self.position() > 3000 or self._index <= 0:
            self.seek_ms(0)
        else:
            self._load(self._index - 1, autoplay=True)

    def seek_ms(self, ms: int):
        self._player.setPosition(int(ms))

    def seek_ratio(self, r: float):
        if self.duration() > 0:
            self.seek_ms(int(self.duration() * r))

    def set_volume(self, v: float):
        self._audio.setVolume(min(1.0, max(0.0, v)))
        self.volumeChanged.emit(self._audio.volume())

    def volume(self) -> float:
        return self._audio.volume()

    def set_shuffle(self, on: bool):
        if on == self._shuffle:
            return
        self._shuffle = on
        cur = self.current
        if on:
            self._orig = list(self._queue)
            start = self._index + 1 if cur else 0
            rest = self._queue[start:]
            random.shuffle(rest)
            self._queue[start:] = rest
        elif self._orig:
            self._queue = self._orig
            self._orig = []
            if cur:
                self._index = next((i for i, t in enumerate(self._queue) if t.id == cur.id), self._index)
        self.modesChanged.emit()

    def cycle_repeat(self):
        self._repeat = {"off": "all", "all": "one", "one": "off"}[self._repeat]
        self.modesChanged.emit()

    def _on_status(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self._pending_seek is not None:
            self._player.setPosition(self._pending_seek)
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            if self._repeat == "one":
                self.seek_ms(0)
                self._player.play()
            else:
                self.next()