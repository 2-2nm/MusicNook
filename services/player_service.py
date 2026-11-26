import random

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from models.track import Track


class PlayerService(QObject):
    trackChanged = Signal(object)
    positionChanged = Signal(int)
    durationChanged = Signal(int)
    playingChanged = Signal(bool)
    volumeChanged = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._player.setAudioOutput(self._audio)
        self._queue: list[Track] = []
        self._index = -1
        self._pending_seek: int | None = None
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

    def position(self) -> int:
        return self._player.position()

    def duration(self) -> int:
        return self._player.duration()

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    # --- control ---
    def play_queue(self, tracks: list[Track], index: int = 0):
        self._queue = list(tracks)
        self._load(index, autoplay=True)

    def shuffle_all(self, tracks: list[Track]):
        q = list(tracks)
        random.shuffle(q)
        if q:
            self.play_queue(q, 0)

    def restore(self, tracks: list[Track], index: int, position_ms: int):
        self._queue = list(tracks)
        self._load(index, autoplay=False, seek=position_ms)

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

    def _on_status(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self._pending_seek is not None:
            self._player.setPosition(self._pending_seek)