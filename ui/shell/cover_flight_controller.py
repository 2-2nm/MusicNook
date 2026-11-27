from PySide6.QtCore import QPoint, QPointF, QRectF, QSizeF
from PySide6.QtWidgets import QGraphicsOpacityEffect

from ui.components.fade_stack import snapshot
from ui.pages.now_playing.stage import COVER_BORDER
from ui.shell.navigation import Page


class CoverFlightController:
    """Library / Playlists <-> Player: the cover of the playing song glides from where it is to where it goes
    (the Continue listening card or the mini player on one side, the big cover on the other), while the pages
    cross-fade. The mini player (hidden on Player) fades out / in with it.

    Works on the main window's parts (pages, mini, card, now_page, player) and the CoverFlight overlay."""

    def __init__(self, win, flight):
        self.win, self.flight = win, flight
        self.to_player = False
        self.via_mini = False  # the Player was opened from the mini player: the cover flies from there
        flight.progressChanged.connect(self._on_progress)

    def finish(self):
        self.flight.finish()

    def can_fly(self, old: int, new: int) -> bool:
        w = self.win
        return ((old == Page.PLAYER) != (new == Page.PLAYER) and w.player.current is not None and w.isVisible()
                and not w.isMinimized() and w.pages.isVisible())

    def _on_progress(self, t: float):
        w = self.win
        if self.to_player:
            w.now_page.stage.set_intro(max(0.0, (t - 0.45) / 0.55))  # record and glow appear as the cover settles
        elif isinstance(w.mini.graphicsEffect(), QGraphicsOpacityEffect):
            w.mini.graphicsEffect().setOpacity(min(1.0, t * 1.6))  # the mini player fades in

    def _end(self):
        """Back to normal: the real covers are drawn again, the mini player is opaque."""
        w = self.win
        w.card.cover.set_ghost(False)
        w.mini.cover.set_ghost(False)
        w.now_page.stage.set_cover_ghost(False)
        w.now_page.stage.set_intro(1.0)
        w.mini.setGraphicsEffect(None)

    def fly(self, old: int, new: int):
        w = self.win
        central, stage, mini = w.centralWidget(), w.now_page.stage, w.mini
        to_player = new == Page.PLAYER
        via_mini, self.via_mini = self.via_mini, False

        def list_cover(page):  # the cover the flight starts from / ends at on the other pages
            return mini.cover if (via_mini or page != Page.LIBRARY) else w.card.cover

        def stage_rect():
            r, radius = stage.cover_rect()
            return r.translated(QPointF(stage.mapTo(central, QPoint(0, 0)))), radius

        def widget_rect(x):
            return QRectF(QPointF(x.mapTo(central, QPoint(0, 0))), QSizeF(x.size()))

        fade_out = None
        if to_player:
            src_w = list_cover(old)
            src, src_radius, src_border = widget_rect(src_w), src_w.radius, 0
            src_w.set_ghost(True)
            stage.set_cover_ghost(True)
            stage.set_intro(0.0)
            w.now_page.show_tab(w.now_tab)
            if mini.isVisible():  # a picture of the mini player (without its cover if that is the one flying)
                fade_out = (snapshot(mini), QPointF(mini.mapTo(central, QPoint(0, 0))))
        else:
            src, src_radius = stage_rect()
            src_border = COVER_BORDER
            stage.set_cover_ghost(True)
            list_cover(new).set_ghost(True)

        def prepare():  # the mini player comes / goes, which resizes the pages
            mini.setVisible(new != Page.PLAYER)
            central.layout().activate()

        w.pages.fade_to(new, prepare)
        central.layout().activate()
        w.now_page.layout().activate()

        if to_player:
            dst, dst_radius = stage_rect()
            dst_border = COVER_BORDER
        else:
            dst_w = list_cover(new)
            dst, dst_radius, dst_border = widget_rect(dst_w), dst_w.radius, 0
            fx = QGraphicsOpacityEffect(mini)  # the mini player fades in while the cover lands
            fx.setOpacity(0.0)
            mini.setGraphicsEffect(fx)

        self.to_player = to_player
        self.flight.start(w.player.current, src, dst, src_radius, dst_radius, src_border, dst_border,
                          fade_out, self._end)
