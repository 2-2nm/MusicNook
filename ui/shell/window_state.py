"""Window size / maximize / minimize / fullscreen bookkeeping, ported from NPI Gallery's main window.

The un-maximized rectangle is tracked here instead of trusting QWidget.saveGeometry() /
normalGeometry(): on Windows Qt can report the maximized rectangle as the "normal" one, which made
Restore (or a relaunch) come back screen-sized.

Usage in the main window (class MainWindow(WindowStateMixin, QMainWindow)):
  * call self._init_window_state() first thing in __init__
  * create self.settings (a QSettings), set the default size, then call self._restore_window_state()
  * set self._ui_ready = True once every child widget exists
  * call self._save_window_state() from closeEvent
"""

import ctypes

from PySide6.QtCore import QEvent, QRect, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from ui.shell.frameless import IS_WINDOWS

SW_MAXIMIZE = 3


class WindowStateMixin:
    def _init_window_state(self) -> None:
        self._normal_rect: QRect | None = None  # last size / place the user gave the window while it was not maximized
        self._fullscreen_from_maximized = False  # where F11 returns to
        self._want_maximized = False
        self._restoring = False
        self._seen_zoomed = False  # True once this run has actually shown the window maximized
        self._restore_attempts = 0
        self._f11_active = False
        self._prev_zoomed = False  # IsZoomed as of the previous state change
        self._ui_ready = False  # restoring the state fires events before the child widgets exist

    # ---------- state queries ----------
    def _in_fullscreen(self) -> bool:
        """True only for the F11 full screen this window asked for.

        QWidget.isFullScreen() cannot be trusted on Windows: Qt flags any window whose geometry equals
        the screen's as full screen, and a maximized window does exactly that when the taskbar is set to
        auto-hide. That made a maximized window look full screen, so it was never saved as maximized.
        """
        return self._f11_active and QWidget.isFullScreen(self)

    def _is_zoomed(self) -> bool:
        """Live maximized state straight from Windows (Qt's isMaximized() lags behind)."""
        if IS_WINDOWS and self.isVisible():
            try:
                return bool(ctypes.windll.user32.IsZoomed(int(self.winId())))
            except Exception:
                pass
        return self.isMaximized()

    def _fills_screen(self, rect: QRect) -> bool:
        # With an auto-hide taskbar availableGeometry() is the whole monitor, while Windows leaves a few
        # pixels of the maximized window out, so an exact ">=" never matched and a maximize in flight
        # was stored as the "normal" size.
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return False
        available = screen.availableGeometry().united(screen.geometry())
        slack = max(16, round(16 * self.devicePixelRatioF()))
        return rect.width() >= available.width() - slack and rect.height() >= available.height() - slack

    # ---------- tracking the normal (un-maximized) rectangle ----------
    def _track_normal_rect(self) -> None:
        if self._restoring or self._want_maximized:
            return
        if not self.isVisible() or self.isMinimized() or self._in_fullscreen() or self._is_zoomed():
            return
        rect = self.geometry()
        # A rectangle as big as the screen is the maximize animation in flight, not a size the user chose.
        if rect.isValid() and not self._fills_screen(rect):
            self._normal_rect = QRect(rect)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._track_normal_rect()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        self._track_normal_rect()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self._ui_ready:
            zoomed = self._is_zoomed()
            left_maximized = self._prev_zoomed and not zoomed
            self._prev_zoomed = zoomed
            # Only a real maximized -> normal transition may move the window. Enforcing on every state
            # change also fired during the startup maximize, and setGeometry() there un-maximized it.
            if left_maximized and not self._restoring:
                QTimer.singleShot(0, self._enforce_normal_rect)
            QTimer.singleShot(150, self._remember_maximized)

    def _enforce_normal_rect(self) -> None:
        """After leaving maximized, put the window back at the size the user had, never at screen size."""
        if self._restoring or self._normal_rect is None or self.isMinimized() or self._in_fullscreen() or self._is_zoomed():
            return
        if self._fills_screen(self.geometry()):
            self.setGeometry(self._fit_to_screens(self._normal_rect))

    def _fit_to_screens(self, rect: QRect) -> QRect:
        """Keep a remembered rectangle on a screen that exists now (a monitor may have been unplugged)."""
        screens = QGuiApplication.screens()
        if not screens:
            return rect
        best, overlap = screens[0], 0
        for screen in screens:
            common = rect.intersected(screen.availableGeometry())
            area = max(0, common.width()) * max(0, common.height())
            if area > overlap:
                best, overlap = screen, area
        available = best.availableGeometry()
        width = min(max(rect.width(), self.minimumWidth()), available.width())
        height = min(max(rect.height(), self.minimumHeight()), available.height())
        if overlap == 0:  # its screen is gone: centre on the primary one
            available = (QGuiApplication.primaryScreen() or best).availableGeometry()
            x = available.x() + (available.width() - width) // 2
            y = available.y() + (available.height() - height) // 2
        else:
            x = min(max(rect.x(), available.left()), available.right() - width + 1)
            y = min(max(rect.y(), available.top()), available.bottom() - height + 1)
        return QRect(x, y, width, height)

    # ---------- restoring at startup ----------
    def _restore_window_state(self) -> None:
        rect = self.settings.value("window/normal_rect")
        if isinstance(rect, QRect) and rect.isValid() and rect.width() > 0 and rect.height() > 0:
            self._normal_rect = QRect(rect)
            self.setGeometry(self._fit_to_screens(rect))
        if self.settings.value("window/maximized", False, bool):
            self._want_maximized = True
            self._restoring = True
            self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._want_maximized:
            self._want_maximized = False
            QTimer.singleShot(0, self._ensure_maximized)

    def _ensure_maximized(self) -> None:
        if self.isMinimized() or self._in_fullscreen():
            self._restoring = False
            return
        if self._is_zoomed():
            self._seen_zoomed = True
            self._restoring = False
            return
        if IS_WINDOWS:
            ctypes.windll.user32.ShowWindow(int(self.winId()), SW_MAXIMIZE)
        else:
            self.showMaximized()
        QTimer.singleShot(250, self._finish_restore)

    def _finish_restore(self) -> None:
        if self.isMinimized() or self._in_fullscreen():
            self._restoring = False
            return
        if self._is_zoomed():
            self._seen_zoomed = True
            self._restoring = False
            return
        # Not maximized yet (Windows can swallow the first request while the window is still being shown,
        # notably with an auto-hide taskbar): ask again a few times before giving up. Giving up leaves the
        # saved "maximized" preference alone, see _maximized_to_save().
        self._restore_attempts += 1
        if self._restore_attempts <= 4:
            self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMaximized)
            self.showMaximized()
            if IS_WINDOWS:
                ctypes.windll.user32.ShowWindow(int(self.winId()), SW_MAXIMIZE)
            QTimer.singleShot(250, self._finish_restore)
            return
        self._restoring = False

    # ---------- persisting ----------
    def _maximized_to_save(self) -> bool | None:
        """What to persist, or None to keep the stored value.

        A failed or still-pending startup restore must never overwrite the saved preference with False;
        that turned one missed maximize into a permanent windowed start.
        """
        if self._in_fullscreen():
            return self._fullscreen_from_maximized
        if self._is_zoomed() or (self.isMaximized() and self._seen_zoomed):
            self._seen_zoomed = True
            return True
        if self._seen_zoomed or not self.settings.value("window/maximized", False, bool):
            return False  # the user really did restore the window (or it was never maximized)
        return None

    def _remember_maximized(self) -> None:
        if self._restoring or not self.isVisible() or self.isMinimized() or self._in_fullscreen():
            return
        value = self._maximized_to_save()
        if value is not None:
            self.settings.setValue("window/maximized", value)
            self.settings.sync()

    def toggle_fullscreen(self) -> None:
        """F11. Leaving full screen goes back to where it came from: maximized, or the remembered size."""
        if self._in_fullscreen():
            self._f11_active = False
            if self._fullscreen_from_maximized:
                self.showMaximized()
            else:
                self.showNormal()
        else:
            self._fullscreen_from_maximized = self._is_zoomed()
            self._f11_active = True
            self.showFullScreen()

    def _save_window_state(self) -> None:
        self._track_normal_rect()
        if self._normal_rect is not None:
            self.settings.setValue("window/normal_rect", self._normal_rect)
        # Closed in full screen: relaunch as what it was before (never start in full screen).
        value = self._maximized_to_save()
        if value is not None:
            self.settings.setValue("window/maximized", value)
        self.settings.sync()