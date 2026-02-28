import os
import platform
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from .logger import LOG_DIR, LOG_FILE
from .settings_manager import SettingsManager
from .theme import get_theme_colors
from .utils import resource_path
from .workers import UpdateWorker


class SettingsDialog(QDialog):
    def __init__(self, settings_manager: SettingsManager, parent=None, current_theme="system"):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.update_worker = None
        self.current_theme = current_theme

        self.setWindowTitle("Settings")
        self.setFixedSize(740, 760)
        self.setModal(True)

        icon_path = resource_path("assets/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._build_ui()
        self._apply_stylesheet()
        self._load_values()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        general_box = QGroupBox("General")
        general_layout = QGridLayout(general_box)
        general_layout.setHorizontalSpacing(20)
        general_layout.setVerticalSpacing(12)
        general_layout.setContentsMargins(14, 18, 14, 14)
        general_layout.setColumnMinimumWidth(0, 240)
        general_layout.setColumnMinimumWidth(1, 420)
        general_layout.setColumnMinimumWidth(2, 120)
        general_layout.setColumnStretch(1, 1)

        lbl_theme = QLabel("Theme")
        general_layout.addWidget(lbl_theme, 0, 0)
        self.cb_theme = QComboBox()
        self.cb_theme.addItem("System (auto)", "system")
        self.cb_theme.addItem("Dark", "dark")
        self.cb_theme.addItem("Light", "light")
        self.cb_theme.setMinimumHeight(34)
        general_layout.addWidget(self.cb_theme, 0, 1, 1, 2)

        lbl_default_folder = QLabel("Default download folder")
        general_layout.addWidget(lbl_default_folder, 1, 0)

        self.input_default_folder = QLineEdit()
        self.input_default_folder.setReadOnly(True)
        self.input_default_folder.setMinimumHeight(34)
        btn_browse = QPushButton("Browse")
        btn_browse.setFixedWidth(120)
        btn_browse.setMinimumHeight(34)
        btn_browse.clicked.connect(self._browse_default_folder)
        general_layout.addWidget(self.input_default_folder, 1, 1)
        general_layout.addWidget(btn_browse, 1, 2)

        lbl_default_mode = QLabel("Default mode")
        general_layout.addWidget(lbl_default_mode, 2, 0)
        self.cb_default_mode = QComboBox()
        self.cb_default_mode.addItems(["Video", "Audio"])
        self.cb_default_mode.setMinimumHeight(34)
        general_layout.addWidget(self.cb_default_mode, 2, 1, 1, 2)

        lbl_audio_format = QLabel("Default audio format")
        general_layout.addWidget(lbl_audio_format, 3, 0)
        self.cb_audio_format = QComboBox()
        self.cb_audio_format.addItems(["mp3", "m4a", "wav", "flac", "opus"])
        self.cb_audio_format.setMinimumHeight(34)
        general_layout.addWidget(self.cb_audio_format, 3, 1, 1, 2)

        lbl_audio_bitrate = QLabel("Default audio bitrate")
        general_layout.addWidget(lbl_audio_bitrate, 4, 0)
        self.cb_audio_bitrate = QComboBox()
        self.cb_audio_bitrate.addItem("320 kbps", "320")
        self.cb_audio_bitrate.addItem("256 kbps", "256")
        self.cb_audio_bitrate.addItem("192 kbps", "192")
        self.cb_audio_bitrate.addItem("128 kbps", "128")
        self.cb_audio_bitrate.addItem("64 kbps", "64")
        self.cb_audio_bitrate.setMinimumHeight(34)
        general_layout.addWidget(self.cb_audio_bitrate, 4, 1, 1, 2)

        downloads_box = QGroupBox("Downloads")
        downloads_layout = QVBoxLayout(downloads_box)
        downloads_layout.setSpacing(8)
        self.chk_clipboard_autopaste = QCheckBox("Auto-paste URL from clipboard on focus")
        self.chk_show_notifications = QCheckBox("Show notification when download completes")
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Speed limit in KB/s (0 = unlimited)"))
        self.spin_speed_limit = QSpinBox()
        self.spin_speed_limit.setRange(0, 100000)
        self.spin_speed_limit.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spin_speed_limit.setSuffix("")
        self.spin_speed_limit.setMaximumWidth(180)
        speed_row.addWidget(self.spin_speed_limit, 1)

        downloads_layout.addWidget(self.chk_clipboard_autopaste)
        downloads_layout.addWidget(self.chk_show_notifications)
        downloads_layout.addLayout(speed_row)

        tray_box = QGroupBox("System Tray")
        tray_layout = QVBoxLayout(tray_box)
        tray_layout.setSpacing(8)
        self.chk_minimize_to_tray = QCheckBox("Minimize to tray on close")
        self.chk_minimize_to_tray.setToolTip(
            "When enabled, closing the window minimizes to system tray instead of quitting. "
            "Use Quit from the tray menu to fully exit."
        )
        self.chk_tray_notifications = QCheckBox("Show tray notifications")
        self.chk_tray_notifications.setToolTip("Show system notifications when downloads complete or fail.")
        tray_layout.addWidget(self.chk_minimize_to_tray)
        tray_layout.addWidget(self.chk_tray_notifications)

        subtitles_box = QGroupBox("Subtitles")
        subtitles_layout = QVBoxLayout(subtitles_box)
        subtitles_layout.setSpacing(8)
        self.chk_include_auto_subs = QCheckBox("Include auto-generated subtitles")
        subtitles_layout.addWidget(self.chk_include_auto_subs)

        maintenance_box = QGroupBox("Maintenance")
        maintenance_layout = QVBoxLayout(maintenance_box)
        maintenance_layout.setSpacing(8)

        update_row = QHBoxLayout()
        self.btn_update = QPushButton("Update yt-dlp")
        self.btn_update.clicked.connect(self._start_update)
        self.lbl_update_status = QLabel("Up to date")
        self.lbl_update_status.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        update_row.addWidget(self.btn_update)
        update_row.addWidget(self.lbl_update_status, 1)
        maintenance_layout.addLayout(update_row)

        logs_row = QHBoxLayout()
        btn_open_log_file = QPushButton("Open log file")
        btn_open_log_folder = QPushButton("Open log folder")
        btn_clear_log_file = QPushButton("Clear log file")
        btn_open_log_file.clicked.connect(self._open_log_file)
        btn_open_log_folder.clicked.connect(self._open_log_folder)
        btn_clear_log_file.clicked.connect(self._clear_log_file)
        logs_row.addWidget(btn_open_log_file)
        logs_row.addWidget(btn_open_log_folder)
        logs_row.addWidget(btn_clear_log_file)
        maintenance_layout.addLayout(logs_row)

        layout.addWidget(general_box)
        layout.addWidget(downloads_box)
        layout.addWidget(tray_box)
        layout.addWidget(subtitles_box)
        layout.addWidget(maintenance_box)

        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        btn_save = QPushButton("Save")
        btn_cancel = QPushButton("Cancel")
        btn_save.setFixedWidth(100)
        btn_cancel.setFixedWidth(100)
        btn_save.clicked.connect(self._save_and_close)
        btn_cancel.clicked.connect(self.reject)
        bottom_bar.addWidget(btn_save)
        bottom_bar.addWidget(btn_cancel)
        layout.addLayout(bottom_bar)

    def _apply_stylesheet(self):
        colors = get_theme_colors(self.current_theme, self.palette())
        bg_color = colors["bg_color"]
        text_color = colors["text_color"]
        border_color = colors["border_color"]
        input_bg = colors["input_bg"]
        btn_bg = colors["btn_bg"]
        btn_hover = colors["btn_hover"]
        btn_text = colors["btn_text"]
        muted_text = colors["muted_text"]
        accent_color = colors["accent_color"]

        self.setStyleSheet(
            f"""
            QDialog {{ background-color: {bg_color}; }}
            QWidget {{ color: {text_color}; font-family: 'Segoe UI', sans-serif; font-size: 13px; }}
            QGroupBox {{ border: 1px solid {border_color}; border-radius: 8px; margin-top: 8px; padding: 8px; font-weight: 600; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; }}
            QLineEdit, QComboBox, QSpinBox {{ background-color: {input_bg}; border: 1px solid {border_color}; border-radius: 5px; padding: 6px; color: {text_color}; }}
            QComboBox QAbstractItemView {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {border_color};
                selection-background-color: {accent_color};
                selection-color: #ffffff;
            }}
            QPushButton {{ background-color: {btn_bg}; color: {btn_text}; border: 1px solid {border_color}; border-radius: 5px; padding: 6px; }}
            QPushButton:hover {{ background-color: {btn_hover}; }}
            QPushButton:focus {{ border: 1px solid {accent_color}; }}
            QPushButton:disabled {{ background-color: {input_bg}; color: {border_color}; }}
            QLabel {{ color: {text_color}; }}
            QCheckBox {{ spacing: 8px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {border_color}; border-radius: 3px; background: {input_bg}; }}
            QCheckBox::indicator:checked {{ background-color: {accent_color}; border-color: {accent_color}; }}
            """
        )
        self.lbl_update_status.setStyleSheet(f"color: {muted_text}; font-weight: 600;")

    def _load_values(self):
        values = self.settings_manager.load()

        theme_value = values[SettingsManager.KEY_THEME]
        theme_index = self.cb_theme.findData(theme_value)
        if theme_index >= 0:
            self.cb_theme.setCurrentIndex(theme_index)

        self.input_default_folder.setText(values[SettingsManager.KEY_DEFAULT_FOLDER])
        self.cb_default_mode.setCurrentText(values[SettingsManager.KEY_DEFAULT_MODE])
        self.cb_audio_format.setCurrentText(values[SettingsManager.KEY_DEFAULT_AUDIO_FORMAT])

        bitrate_value = values[SettingsManager.KEY_DEFAULT_AUDIO_BITRATE]
        bitrate_index = self.cb_audio_bitrate.findData(bitrate_value)
        if bitrate_index >= 0:
            self.cb_audio_bitrate.setCurrentIndex(bitrate_index)

        self.chk_clipboard_autopaste.setChecked(values[SettingsManager.KEY_CLIPBOARD_AUTOPASTE])
        self.chk_show_notifications.setChecked(values[SettingsManager.KEY_SHOW_NOTIFICATIONS])
        self.spin_speed_limit.setValue(values[SettingsManager.KEY_SPEED_LIMIT])
        self.chk_minimize_to_tray.setChecked(values[SettingsManager.KEY_MINIMIZE_TO_TRAY])
        self.chk_tray_notifications.setChecked(values[SettingsManager.KEY_TRAY_NOTIFICATIONS])
        self.chk_include_auto_subs.setChecked(values[SettingsManager.KEY_INCLUDE_AUTO_SUBS])

    def _browse_default_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", self.input_default_folder.text())
        if folder:
            self.input_default_folder.setText(folder)

    def _open_log_file(self):
        log_file = Path(LOG_FILE)
        if not log_file.exists():
            QMessageBox.information(self, "Log file", "No log file found")
            return

        if platform.system() == "Windows":
            os.startfile(str(log_file))
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(log_file)])
        else:
            subprocess.Popen(["xdg-open", str(log_file)])

    def _open_log_folder(self):
        log_folder = str(LOG_DIR)
        os.makedirs(log_folder, exist_ok=True)

        if platform.system() == "Windows":
            os.startfile(log_folder)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", log_folder])
        else:
            subprocess.Popen(["xdg-open", log_folder])

    def _clear_log_file(self):
        log_file = Path(LOG_FILE)
        if not log_file.exists():
            QMessageBox.information(self, "Log file", "No log file found")
            return

        answer = QMessageBox.question(
            self,
            "Clear log file",
            "Are you sure you want to clear the log file?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        log_file.write_text("", encoding="utf-8")
        QMessageBox.information(self, "Log file", "Log file cleared")

    def _start_update(self):
        if self.update_worker is not None and self.update_worker.isRunning():
            return

        self.btn_update.setEnabled(False)
        self.lbl_update_status.setText("Updating...")

        self.update_worker = UpdateWorker()
        self.update_worker.finished_signal.connect(self._on_update_finished)
        self.update_worker.error_signal.connect(self._on_update_error)
        self.update_worker.start()

    def _on_update_finished(self, message):
        self.lbl_update_status.setText("Up to date")
        self.btn_update.setEnabled(True)
        self.update_worker = None
        QMessageBox.information(self, "yt-dlp Update", message)

    def _on_update_error(self, error_message):
        self.lbl_update_status.setText("Update failed")
        self.btn_update.setEnabled(True)
        self.update_worker = None
        QMessageBox.warning(self, "yt-dlp Update", error_message)

    def _save_and_close(self):
        settings_dict = {
            SettingsManager.KEY_THEME: str(self.cb_theme.currentData()),
            SettingsManager.KEY_DEFAULT_FOLDER: self.input_default_folder.text().strip() or str(Path.home() / "Downloads"),
            SettingsManager.KEY_DEFAULT_MODE: self.cb_default_mode.currentText(),
            SettingsManager.KEY_DEFAULT_AUDIO_FORMAT: self.cb_audio_format.currentText(),
            SettingsManager.KEY_DEFAULT_AUDIO_BITRATE: str(self.cb_audio_bitrate.currentData()),
            SettingsManager.KEY_CLIPBOARD_AUTOPASTE: self.chk_clipboard_autopaste.isChecked(),
            SettingsManager.KEY_SHOW_NOTIFICATIONS: self.chk_show_notifications.isChecked(),
            SettingsManager.KEY_SPEED_LIMIT: self.spin_speed_limit.value(),
            SettingsManager.KEY_MINIMIZE_TO_TRAY: self.chk_minimize_to_tray.isChecked(),
            SettingsManager.KEY_TRAY_NOTIFICATIONS: self.chk_tray_notifications.isChecked(),
            SettingsManager.KEY_INCLUDE_AUTO_SUBS: self.chk_include_auto_subs.isChecked(),
        }
        self.settings_manager.save(settings_dict)
        self.accept()
