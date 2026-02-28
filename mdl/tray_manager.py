from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QMenu,
    QStyle,
    QSystemTrayIcon,
)


class TrayManager(QObject):
    quit_requested = pyqtSignal()

    def __init__(self, main_window, icon_path):
        super().__init__(main_window)
        self.main_window = main_window
        self.available = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray_icon = None
        self.menu = None
        self.action_toggle = None
        self.action_status = None
        self.action_quit = None

        if not self.available:
            return

        icon = QIcon(icon_path)
        if not icon_path or icon.isNull():
            icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)

        self.tray_icon = QSystemTrayIcon(icon, self.main_window)
        self.tray_icon.setToolTip("Media Downloader")

        self.menu = QMenu(self.main_window)

        self.action_toggle = self.menu.addAction("Show / Hide")
        self.action_toggle.triggered.connect(self.toggle_window_visibility)

        self.menu.addSeparator()
        self.action_status = self.menu.addAction("Currently: Idle")
        self.action_status.setEnabled(False)

        self.menu.addSeparator()
        self.action_quit = self.menu.addAction("Quit")
        self.action_quit.triggered.connect(self._request_quit)

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.activated.connect(self._on_activated)
        self.tray_icon.messageClicked.connect(self.show_main_window)

    def show(self):
        if self.available and self.tray_icon is not None:
            self.tray_icon.show()

    def _request_quit(self):
        self.quit_requested.emit()

    def _on_activated(self, reason):
        if reason in {
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        }:
            self.toggle_window_visibility()

    def show_main_window(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def toggle_window_visibility(self):
        if self.main_window.isVisible() and not self.main_window.isMinimized():
            self.main_window.hide()
        else:
            self.show_main_window()

    def _show_message(self, title, message, icon, duration_ms):
        if not self.available or self.tray_icon is None:
            return
        self.tray_icon.showMessage(title, message, icon, duration_ms)

    def notify_download_complete(self, title):
        self._show_message(
            "Download Complete",
            f"Finished: {title}",
            QSystemTrayIcon.MessageIcon.Information,
            5000,
        )

    def notify_download_error(self, title, error):
        self._show_message(
            "Download Failed",
            f"{title}: {error}",
            QSystemTrayIcon.MessageIcon.Warning,
            5000,
        )

    def notify_queue_complete(self, succeeded, failed, cancelled):
        self._show_message(
            "Queue Complete",
            f"{succeeded} succeeded, {failed} failed, {cancelled} cancelled",
            QSystemTrayIcon.MessageIcon.Information,
            7000,
        )

    def set_status_idle(self):
        if self.action_status is not None:
            self.action_status.setText("Currently: Idle")
        if self.tray_icon is not None:
            self.tray_icon.setToolTip("Media Downloader")

    def set_status_downloading(self, title=""):
        normalized = str(title or "").strip()
        if len(normalized) > 40:
            normalized = normalized[:37].rstrip() + "..."

        text = "Currently: Downloading..."
        if normalized:
            text = f"Currently: Downloading {normalized}"

        if self.action_status is not None:
            self.action_status.setText(text)
        if self.tray_icon is not None:
            self.tray_icon.setToolTip("Media Downloader - Downloading...")

    def set_status_queue(self, remaining):
        if self.action_status is not None:
            self.action_status.setText(f"Currently: Processing queue ({int(max(0, remaining))} remaining)")
        if self.tray_icon is not None:
            self.tray_icon.setToolTip("Media Downloader - Downloading...")

    def shutdown(self):
        if self.tray_icon is not None:
            self.tray_icon.hide()
