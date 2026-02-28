import os
import platform
import subprocess
import tempfile
from pathlib import Path

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)
from .config import AUDIO_FORMATS, LANGUAGE_NAMES
from .logger import logger
from .queue_manager import QueueManager
from .queue_widget import QueueWidget
from .settings_dialog import SettingsDialog
from .settings_manager import SettingsManager
from .tray_manager import TrayManager
from .theme import get_theme_colors
from .utils import get_disk_space, get_ffmpeg_location, resource_path
from .workers import DownloadWorker, InfoWorker


# This file defines the main window of the Media Downloader application.
# It contains the UI layout, event handlers, and logic for fetching video information and downloading videos.


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Media Downloader")
        self._collapsed_size = (850, 560)
        self._expanded_size = (850, 760)
        self.setFixedSize(*self._collapsed_size)

        icon_path = resource_path("assets/icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.download_folder = str(Path.home() / "Downloads")
        self.video_info = {}
        self.video_formats = []
        self.subtitle_languages = []
        self.auto_subtitle_languages = []

        self.fetch_timer = QTimer()
        self.fetch_timer.setSingleShot(True)
        self.fetch_timer.timeout.connect(self.start_fetch_info)

        self.status_anim_timer = QTimer()
        self.status_anim_timer.setInterval(450)
        self.status_anim_timer.timeout.connect(self._tick_status_animation)
        self._status_anim_base = ""
        self._status_anim_step = 0

        self.download_worker = None
        self.info_worker = None
        self.queue_manager = QueueManager()
        self._queue_active = False
        self._current_queue_index = None
        self._queue_summary = {"finished": 0, "error": 0, "cancelled": 0}
        self._queue_cancel_requested = False
        self.settings_manager = SettingsManager()
        saved_theme = self.settings_manager.get_theme()
        self.current_settings = self.settings_manager.load()
        self._current_theme = "dark"
        self._yt_dlp_version = None
        self._app_version = None
        self._tray_close_notice_shown = False
        self._force_app_quit = False
        self.tray_manager = None

        self.setup_ui()
        self.apply_stylesheet(theme=saved_theme)
        self.tray_manager = TrayManager(self, resource_path("assets/icon.ico"))
        if self.tray_manager.available:
            self.tray_manager.quit_requested.connect(self.on_tray_quit_requested)
            self.tray_manager.show()
        self.apply_loaded_settings()
        self.update_system_info()
        self.update_output_indicator()
        self._update_download_button_text()

    def setup_ui(self):
        control_height = 40

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        # Header
        header_layout = QHBoxLayout()
        title_lbl = QLabel("Media Downloader")
        title_lbl.setObjectName("TitleLabel")
        title_lbl.setStyleSheet("font-size: 24px; font-weight: 700;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_help = QPushButton("?")
        self.btn_help.setFixedSize(30, 30)
        self.btn_help.clicked.connect(self.show_app_help)

        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setFixedSize(30, 30)
        self.btn_settings.setToolTip("Open settings")
        self.btn_settings.clicked.connect(self.open_settings_dialog)

        left_header_spacer = QWidget()
        left_header_spacer.setFixedSize(60, 30)
        header_layout.addWidget(left_header_spacer)
        header_layout.addStretch()
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_settings)
        header_layout.addWidget(self.btn_help)
        layout.addLayout(header_layout)

        # Input
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste link (URL) - Ctrl+V")
        self.url_input.setMinimumHeight(control_height)
        self.url_input.textChanged.connect(self.on_url_change)

        self.fetch_btn = QPushButton("Fetch")
        self.fetch_btn.setMinimumHeight(control_height)
        self.fetch_btn.setFixedWidth(100)
        self.fetch_btn.clicked.connect(self.start_fetch_info)

        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.fetch_btn)
        layout.addLayout(url_layout)

        # Top settings: Type + Playlist + Output
        top_settings_row = QHBoxLayout()
        top_settings_row.setSpacing(8)

        settings_frame = QFrame()
        settings_frame.setObjectName("SettingsFrame")
        settings_layout = QHBoxLayout(settings_frame)
        settings_layout.setContentsMargins(10, 8, 10, 8)
        settings_layout.setSpacing(8)

        self.rb_group = QButtonGroup()
        self.rb_video = QRadioButton("Video")
        self.rb_audio = QRadioButton("Audio")
        self.rb_video.setToolTip("Download video with audio.")
        self.rb_audio.setToolTip("Extract audio only (no video).")
        self.rb_video.setChecked(True)
        self.rb_group.addButton(self.rb_video)
        self.rb_group.addButton(self.rb_audio)
        self.rb_video.toggled.connect(self.update_ui_state)

        settings_layout.addWidget(QLabel("Type:"))
        settings_layout.addWidget(self.rb_video)
        settings_layout.addWidget(self.rb_audio)
        settings_layout.addSpacing(12)

        self.cb_download_playlist = QCheckBox("Playlist")
        self.cb_download_playlist.setToolTip("When enabled, playlist URLs download all items into a playlist folder.")
        settings_layout.addWidget(self.cb_download_playlist)

        settings_layout.addStretch()

        output_frame = QFrame()
        output_frame.setObjectName("SettingsFrame")
        output_frame.setFixedWidth(130)
        output_layout = QHBoxLayout(output_frame)
        output_layout.setContentsMargins(10, 8, 10, 8)

        self.lbl_output_indicator = QLabel("Output: -")
        self.lbl_output_indicator.setObjectName("OutputIndicator")
        self.lbl_output_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_output_indicator.setToolTip("Shows the final output extension.")
        output_layout.addWidget(self.lbl_output_indicator)

        top_settings_row.addWidget(settings_frame, 1)
        top_settings_row.addWidget(output_frame)
        layout.addLayout(top_settings_row)

        # Lower settings: format / fps / quality / subtitles
        options_frame = QFrame()
        options_frame.setObjectName("SettingsFrame")
        options_layout = QHBoxLayout(options_frame)
        options_layout.setContentsMargins(10, 8, 10, 8)
        options_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        options_layout.setSpacing(6)

        self.lbl_quality = QLabel("Quality:")
        self.lbl_quality.setFixedWidth(50)
        self.lbl_quality.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.lbl_quality.setToolTip("Select resolution (video) or bitrate (audio).")
        options_layout.addWidget(self.lbl_quality)
        self.cb_quality = QComboBox()
        self.cb_quality.setFixedWidth(150)
        self.cb_quality.setToolTip("Select resolution (video) or bitrate (audio).")
        self.cb_quality.setEnabled(False)
        options_layout.addWidget(self.cb_quality)

        self.lbl_format = QLabel("Format:")
        self.lbl_format.setFixedWidth(50)
        self.lbl_format.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self.lbl_format.setToolTip("Choose output format/container.")
        options_layout.addWidget(self.lbl_format)
        self.cb_format = QComboBox()
        self.cb_format.setFixedWidth(150)
        self.cb_format.setToolTip("Choose output format/container.")
        self.cb_format.currentIndexChanged.connect(self.on_format_changed)
        options_layout.addWidget(self.cb_format)

        self.lbl_fps = QLabel("FPS:")
        self.lbl_fps.setFixedWidth(32)
        self.lbl_fps.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self.lbl_fps.setToolTip("Choose frame rate for video mode.")
        options_layout.addWidget(self.lbl_fps)
        self.cb_fps = QComboBox()
        self.cb_fps.setFixedWidth(72)
        self.cb_fps.setToolTip("Choose frame rate for video mode.")
        self.cb_fps.currentIndexChanged.connect(self.on_fps_changed)
        options_layout.addWidget(self.cb_fps)

        self.lbl_subtitles = QLabel("Subtitles:")
        self.lbl_subtitles.setFixedWidth(62)
        self.lbl_subtitles.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self.lbl_subtitles.setToolTip("Include subtitles in the output file.")
        options_layout.addWidget(self.lbl_subtitles)
        self.cb_subtitles = QComboBox()
        self.cb_subtitles.setFixedWidth(150)
        self.cb_subtitles.setToolTip("Selecting subtitles changes output container to MKV.")
        self.cb_subtitles.currentIndexChanged.connect(self.update_output_indicator)
        options_layout.addWidget(self.cb_subtitles)

        options_layout.addStretch()

        self.set_subtitle_options([])

        layout.addWidget(options_frame)

        # Folder
        folder_layout = QHBoxLayout()
        self.btn_open_folder = QPushButton("📂 Open")
        self.btn_open_folder.setMinimumHeight(control_height)
        self.btn_open_folder.clicked.connect(self.open_folder)
        self.lbl_folder = QLineEdit(self.download_folder)
        self.lbl_folder.setMinimumHeight(control_height)
        self.lbl_folder.setReadOnly(True)
        self.btn_change_folder = QPushButton("Change")
        self.btn_change_folder.setMinimumHeight(control_height)
        self.btn_change_folder.clicked.connect(self.change_folder)
        folder_layout.addWidget(self.btn_open_folder)
        folder_layout.addWidget(self.lbl_folder)
        folder_layout.addWidget(self.btn_change_folder)
        layout.addLayout(folder_layout)

        # Queue
        self.queue_widget = QueueWidget(self.queue_manager)
        self.queue_widget.queue_changed.connect(self.on_queue_changed)
        self.queue_widget.expanded_changed.connect(self.on_queue_expanded_changed)
        self.queue_widget.clear_all_requested.connect(self.on_clear_queue_requested)
        layout.addWidget(self.queue_widget)

        # Status
        self.lbl_system_info = QLabel("Loading info...")
        self.lbl_system_info.setObjectName("SystemInfoLabel")
        self.lbl_system_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_system_info.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.lbl_system_info)

        self.lbl_status = QLabel("Ready")
        self.lbl_status.setObjectName("StatusLabel")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 600; color: #b8c2d1;")
        layout.addWidget(self.lbl_status)

        # Progress
        self.progress_bar = QProgressBar()
        sp = self.progress_bar.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        self.progress_bar.setSizePolicy(sp)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_add_queue = QPushButton("ADD TO QUEUE")
        self.btn_add_queue.setMinimumHeight(50)
        self.btn_add_queue.setStyleSheet("background-color: #3a587e; color: white; font-weight: 600; font-size: 13px; border-radius: 6px;")
        self.btn_add_queue.clicked.connect(self.add_to_queue)

        self.btn_download = QPushButton("DOWNLOAD")
        self.btn_download.setMinimumHeight(50)
        self.btn_download.setStyleSheet("background-color: #2f8a3a; color: white; font-weight: 600; font-size: 13px; border-radius: 6px;")
        self.btn_download.clicked.connect(self.start_download)
        self.btn_download.setEnabled(False)

        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.setMinimumHeight(50)
        self.btn_cancel.setStyleSheet("background-color: #b63a3a; color: white; font-weight: 600; font-size: 13px; border-radius: 6px;")
        self.btn_cancel.clicked.connect(self.cancel_download)
        self.btn_cancel.setEnabled(False)

        btn_layout.addWidget(self.btn_add_queue, 2)
        btn_layout.addWidget(self.btn_download, 2)
        btn_layout.addWidget(self.btn_cancel, 1)
        layout.addLayout(btn_layout)

    def apply_stylesheet(self, theme=None):
        colors = get_theme_colors(theme, self.palette())
        self._current_theme = colors["resolved_theme"]

        bg_color = colors["bg_color"]
        text_color = colors["text_color"]
        border_color = colors["border_color"]
        input_bg = colors["input_bg"]
        btn_bg = colors["btn_bg"]
        btn_hover = colors["btn_hover"]
        btn_text = colors["btn_text"]
        muted_text = colors["muted_text"]
        placeholder = colors["placeholder"]
        accent_color = colors["accent_color"]

        stylesheet = f"""
            QMainWindow {{ background-color: {bg_color}; }}
            QWidget {{ color: {text_color}; font-family: 'Segoe UI', sans-serif; font-size: 13px; }}
            QMessageBox {{ background-color: {bg_color}; }}
            QMessageBox QLabel {{ color: {text_color}; }}
            QLineEdit {{ background-color: {input_bg}; border: 1px solid {border_color}; border-radius: 5px; padding: 6px; color: {text_color}; }}
            QLineEdit:focus {{ border: 1px solid {accent_color}; }}
            QLineEdit::placeholder {{ color: {placeholder}; }}
            QComboBox {{ background-color: {input_bg}; border: 1px solid {border_color}; border-radius: 5px; padding: 6px; color: {text_color}; }}
            QComboBox:focus {{ border: 1px solid {accent_color}; }}
            QComboBox::drop-down {{ border: 0px; }}
            QComboBox QAbstractItemView {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {border_color};
                selection-background-color: {accent_color};
                selection-color: #ffffff;
            }}
            QPushButton {{
                background-color: {btn_bg};
                color: {btn_text};
                border: 1px solid {border_color};
                border-radius: 5px;
                padding: 6px;
                }}
            QPushButton:hover {{background-color: {btn_hover}; }}
            QPushButton:focus {{ border: 1px solid {accent_color}; }}
            QPushButton:disabled {{background-color: {input_bg}; color: {border_color}; }}
            QCheckBox {{ spacing: 8px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {border_color}; border-radius: 3px; background: {input_bg}; }}
            QCheckBox::indicator:checked {{ background-color: {accent_color}; border-color: {accent_color}; }}
            QProgressBar {{ border: 1px solid {border_color}; border-radius: 4px; text-align: center; background-color: {input_bg}; }}
            QProgressBar::chunk {{ background-color: {accent_color}; border-radius: 3px; }}
            QFrame#SettingsFrame {{ background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 8px; padding: 6px; }}
            QLabel#TitleLabel {{ color: {accent_color}; }}
            QLabel#SystemInfoLabel {{ color: {muted_text}; }}
            QLabel#OutputIndicator {{ color: {text_color}; font-size: 12px; font-weight: 600; }}
            QLabel#StatusLabel {{ color: {muted_text}; }}
        """
        self.setStyleSheet(stylesheet)
        if hasattr(self, 'queue_widget'):
            self.queue_widget.set_theme(theme or self.settings_manager.get_theme())

    def on_url_change(self):
        self.fetch_timer.start(350)
        self._update_download_button_text()

    def _is_tray_notification_enabled_and_hidden(self):
        tray_enabled = self.settings_manager.get_tray_notifications()
        hidden = self.isHidden() or (not self.isVisible())
        return tray_enabled and hidden and self.tray_manager is not None and self.tray_manager.available

    def _get_active_download_title(self):
        title = str((self.video_info or {}).get("title") or "").strip()
        return title or "Download"

    def start_status_animation(self, base_text):
        self._status_anim_base = base_text.rstrip(". ")
        self._status_anim_step = 0
        if not self.status_anim_timer.isActive():
            self.status_anim_timer.start()
        self._tick_status_animation()

    def stop_status_animation(self):
        if self.status_anim_timer.isActive():
            self.status_anim_timer.stop()
        self._status_anim_base = ""
        self._status_anim_step = 0

    def _tick_status_animation(self):
        if not self._status_anim_base:
            return
        dots = "." * ((self._status_anim_step % 3) + 1)
        self.lbl_status.setText(f"{self._status_anim_base}{dots}")
        self._status_anim_step += 1

    def start_fetch_info(self):
        if self.info_worker and self.info_worker.isRunning():
            return

        url = self.url_input.text().strip()
        if not url or (not url.startswith("http") and "www" not in url):
            return

        self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 600; color: #b8c2d1;")
        self.start_status_animation("Fetching information")
        self.fetch_btn.setEnabled(False)
        self.btn_download.setEnabled(False)

        self.info_worker = InfoWorker(url)
        self.info_worker.finished_signal.connect(self.on_info_fetched)
        self.info_worker.error_signal.connect(self.on_info_error)
        self.info_worker.start()

    def on_info_fetched(self, info, formats, subtitle_languages, auto_subtitle_languages):
        self.stop_status_animation()
        self.info_worker = None
        self.video_info = info
        self.video_formats = formats
        self.subtitle_languages = [
            lang for lang in subtitle_languages
            if self._is_supported_subtitle_language(lang)
        ]
        self.auto_subtitle_languages = [
            lang for lang in auto_subtitle_languages
            if self._is_supported_subtitle_language(lang)
        ]
        self.set_subtitle_options(self.subtitle_languages, self.auto_subtitle_languages)
        self.lbl_status.setText(f"Loaded: {info.get('title')}")
        self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 600; color: #9cc06b;")
        self.fetch_btn.setEnabled(True)
        self.update_ui_state()

        if self._queue_active and self._current_queue_index is not None:
            queue_items = self.queue_manager.get_all()
            if 0 <= self._current_queue_index < len(queue_items):
                self._apply_queue_item_options(queue_items[self._current_queue_index])
            self.queue_manager.update_title(self._current_queue_index, info.get('title') or self.url_input.text().strip())
            self.queue_widget.refresh_item(self._current_queue_index)

            if self._queue_cancel_requested:
                self._mark_current_queue_item_cancelled()
                self.process_queue()
                return

            self._start_download_for_url(self.url_input.text().strip())

    def on_info_error(self, err):
        self.stop_status_animation()
        self.info_worker = None
        logger.warning("Info fetch error: %s", err)
        self.lbl_status.setText(f"Error: {err[:50]}...")
        self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 600; color: #d98787;")
        self.fetch_btn.setEnabled(True)
        self.subtitle_languages = []
        self.auto_subtitle_languages = []
        self.set_subtitle_options([], [])
        self._update_download_button_text()

        if self._queue_active and self._current_queue_index is not None:
            self.queue_manager.update_status(self._current_queue_index, "error", err)
            self.queue_widget.refresh_item(self._current_queue_index)
            self._queue_summary["error"] += 1
            self._current_queue_index = None
            self.process_queue()

    def set_subtitle_options(self, subtitle_languages, auto_subtitle_languages=None):
        if auto_subtitle_languages is None:
            auto_subtitle_languages = []

        include_auto_subs = self.settings_manager.get_include_auto_subs()
        if not include_auto_subs:
            auto_subtitle_languages = []

        self.cb_subtitles.blockSignals(True)
        self.cb_subtitles.clear()
        self.cb_subtitles.addItem("None", None)

        has_any_subtitles = bool(subtitle_languages or auto_subtitle_languages)
        if has_any_subtitles:
            self.cb_subtitles.addItem("All available", "__all__")
            for lang in subtitle_languages:
                self.cb_subtitles.addItem(self.get_language_display_name(lang), ("manual", lang))

            for lang in auto_subtitle_languages:
                if lang in subtitle_languages:
                    continue
                self.cb_subtitles.addItem(f"{self.get_language_display_name(lang)} [auto]", ("auto", lang))

        self.cb_subtitles.blockSignals(False)
        self.update_output_indicator()

    def get_language_display_name(self, language_code):
        base_code = language_code.lower().split("-")[0].split("_")[0]
        language_name = LANGUAGE_NAMES.get(base_code)

        if language_name:
            return f"{language_name} ({language_code})"
        return language_code.upper()

    def _is_supported_subtitle_language(self, language_code):
        base_code = language_code.lower().split("-")[0].split("_")[0]
        return base_code in LANGUAGE_NAMES

    def update_ui_state(self):
        is_audio = self.rb_audio.isChecked()

        self.cb_format.blockSignals(True)
        self.cb_fps.blockSignals(True)
        self.cb_quality.blockSignals(True)

        self.cb_format.clear()
        self.cb_fps.clear()
        self.cb_quality.clear()

        if is_audio:
            self.lbl_fps.setVisible(False)
            self.cb_fps.setVisible(False)
            self.lbl_subtitles.setVisible(False)
            self.cb_subtitles.setVisible(False)
            self.lbl_format.setText("Format:")

            self.cb_format.addItems(["mp3", "m4a", "wav", "flac", "opus"])

            bitrates = ["320", "256", "192", "128", "64"]
            for b in bitrates:
                self.cb_quality.addItem(f"{b} kbps", b)

            self.cb_quality.setEnabled(True)
            self.btn_download.setEnabled(bool(self.url_input.text()))
        else:
            self.lbl_fps.setVisible(True)
            self.cb_fps.setVisible(True)
            self.lbl_subtitles.setVisible(True)
            self.cb_subtitles.setVisible(True)
            self.lbl_format.setText("Format:")

            if self.video_formats:
                self.populate_video_formats()
                self.btn_download.setEnabled(True)
                self.cb_quality.setEnabled(True)
            else:
                self.cb_quality.addItem("Fetch link first...")
                self.cb_quality.setEnabled(False)
                self.btn_download.setEnabled(False)

        self.cb_format.blockSignals(False)
        self.cb_fps.blockSignals(False)
        self.cb_quality.blockSignals(False)
        self._update_download_button_text()
        self.update_output_indicator()

    def populate_video_formats(self):
        unique_formats = set()
        combo_items = []

        for f in self.video_formats:
            ext = f.get('ext')
            codec = f.get('vcodec_clean')
            key = (ext, codec)
            if key not in unique_formats:
                unique_formats.add(key)
                display_text = f"{ext} ({codec})"
                combo_items.append((display_text, key))

        combo_items.sort(key=lambda x: x[0])
        for text, data in combo_items:
            self.cb_format.addItem(text, data)
        self.on_format_changed()

    def on_format_changed(self):
        self.cb_fps.blockSignals(True)
        self.cb_fps.clear()

        selected_data = self.cb_format.currentData()
        if not selected_data:
            self.cb_fps.blockSignals(False)
            self.update_output_indicator()
            return

        sel_ext, sel_codec = selected_data
        unique_fps = set()

        for f in self.video_formats:
            if f.get('ext') == sel_ext and f.get('vcodec_clean') == sel_codec:
                unique_fps.add(f.get('fps_rounded', 0))

        sorted_fps = sorted(list(unique_fps), reverse=True)
        for fps in sorted_fps:
            self.cb_fps.addItem(str(fps), fps)

        self.cb_fps.blockSignals(False)
        self.on_fps_changed()
        self.update_output_indicator()

    def update_output_indicator(self):
        if not hasattr(self, 'lbl_output_indicator'):
            return

        if self.rb_audio.isChecked():
            audio_ext = self.cb_format.currentText() or "audio"
            self.lbl_output_indicator.setText(f"Output: .{audio_ext}")
            self.lbl_output_indicator.setStyleSheet("color: #b8c2d1;")
            return

        if self.cb_subtitles.currentData() is not None:
            self.lbl_output_indicator.setText("Output: .mkv")
            self.lbl_output_indicator.setStyleSheet("color: #7dc0ff;")
            return

        fmt_data = self.cb_format.currentData()
        video_ext = fmt_data[0] if fmt_data else "mp4"
        self.lbl_output_indicator.setText(f"Output: .{video_ext}")
        self.lbl_output_indicator.setStyleSheet("color: #b8c2d1;")

    def on_fps_changed(self):
        self.cb_quality.blockSignals(True)
        self.cb_quality.clear()

        selected_fmt_data = self.cb_format.currentData()
        selected_fps = self.cb_fps.currentData()

        if not selected_fmt_data or selected_fps is None:
            return

        sel_ext, sel_codec = selected_fmt_data
        candidates = [
            f for f in self.video_formats
            if f.get('ext') == sel_ext and f.get('vcodec_clean') == sel_codec
        ]

        res_groups = {}
        for f in candidates:
            h = f.get('height', 0)
            if h not in res_groups:
                res_groups[h] = []
            res_groups[h].append(f)

        sorted_heights = sorted(res_groups.keys(), reverse=True)

        for h in sorted_heights:
            group = res_groups[h]
            match = next((f for f in group if f.get('fps_rounded') == selected_fps), None)
            final_f = match if match else group[0]

            res_str = f"{final_f['width']}x{final_f['height']}"
            f_id = final_f['format_id']

            display = res_str
            if final_f['fps_rounded'] != selected_fps:
                display += f" | {final_f['fps_rounded']} fps"

            self.cb_quality.addItem(display, f_id)

        self.cb_quality.blockSignals(False)

    def show_app_help(self):
        help_text = (
            "<h3>App Guide</h3>"
            "<ul>"
            "<li><b>Fetch:</b> Retrieving video metadata from the provided URL.</li>"
            "<li><b>Type (Video/Audio):</b> Choose full video download or audio extraction only.</li>"
            "<li><b>Format:</b> Select preferred video codec/container or audio format.</li>"
            "<li><b>FPS:</b> Choose framerate for video mode; quality list adapts to your selection.</li>"
            "<li><b>Subtitles:</b> Embeds subtitles into the video (None, one language, or All available).</li>"
            "<li><b>Quality:</b> Choose resolution (video) or bitrate (audio).</li>"
            "<li><b>Output file:</b> Shows final extension. If subtitles are selected in video mode, output changes to <b>.mkv</b>.</li>"
            "<li><b>Filename suffix:</b> Video files include selected resolution and codec at the end (for example [1920x1080 av01]).</li>"
            "<li><b>Playlist:</b> Off by default. Enable it only when you want to download every item from a playlist URL.</li>"
            "</ul>"
            "<p><i>Note: FFmpeg is recommended for best results and required for some post-processing actions.</i></p>"
        )
        QMessageBox.information(self, "App Help", help_text)

    def open_settings_dialog(self):
        current_theme = self.settings_manager.get_theme()
        dialog = SettingsDialog(self.settings_manager, self, current_theme=current_theme)
        if dialog.exec():
            new_theme = self.settings_manager.get_theme()
            self.apply_stylesheet(theme=new_theme)
            self.apply_loaded_settings()
            self.update_system_info()

    def apply_loaded_settings(self):
        self.current_settings = self.settings_manager.load()

        self.download_folder = self.current_settings[SettingsManager.KEY_DEFAULT_FOLDER]
        if hasattr(self, 'lbl_folder'):
            self.lbl_folder.setText(self.download_folder)

        default_mode = self.current_settings[SettingsManager.KEY_DEFAULT_MODE]
        if default_mode == "Audio":
            self.rb_audio.setChecked(True)
        else:
            self.rb_video.setChecked(True)

        self.update_ui_state()

        if self.rb_audio.isChecked():
            default_format = self.current_settings[SettingsManager.KEY_DEFAULT_AUDIO_FORMAT]
            default_bitrate = self.current_settings[SettingsManager.KEY_DEFAULT_AUDIO_BITRATE]

            format_index = self.cb_format.findText(default_format)
            if format_index >= 0:
                self.cb_format.setCurrentIndex(format_index)

            bitrate_index = self.cb_quality.findData(default_bitrate)
            if bitrate_index >= 0:
                self.cb_quality.setCurrentIndex(bitrate_index)

        self.set_subtitle_options(self.subtitle_languages, self.auto_subtitle_languages)

        self.update_output_indicator()

    def _build_base_ydl_opts(self, temp_dir, playlist_mode):
        if playlist_mode:
            outtmpl = os.path.join(
                self.download_folder,
                '%(playlist_title)s',
                '%(playlist_index)03d - %(title)s.%(ext)s',
            )
            home_path = self.download_folder
        else:
            outtmpl = os.path.join(temp_dir, '%(title)s.%(ext)s')
            home_path = temp_dir

        ydl_opts = {
            'outtmpl': outtmpl,
            'paths': {'home': home_path},
            'quiet': True,
            'no_warnings': True,
            'overwrites': True,
            'noplaylist': not playlist_mode,
        }

        loc_ffmpeg = get_ffmpeg_location()
        if loc_ffmpeg:
            ydl_opts['ffmpeg_location'] = loc_ffmpeg

        speed_limit_kb = self.settings_manager.get_speed_limit()
        if speed_limit_kb > 0:
            ydl_opts['ratelimit'] = speed_limit_kb * 1024

        return ydl_opts

    def _build_audio_download_options(self, ydl_opts):
        target_ext = self.cb_format.currentText()
        bitrate = self.cb_quality.currentData()

        ydl_opts['format'] = 'bestaudio/best'
        postprocessors = [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': target_ext,
                'preferredquality': bitrate,
            }
        ]

        conf = AUDIO_FORMATS.get(target_ext, {})
        if conf.get('thumb'):
            postprocessors.append({'key': 'EmbedThumbnail'})
        if conf.get('meta'):
            postprocessors.append({'key': 'FFmpegMetadata'})

        ydl_opts['postprocessors'] = postprocessors
        file_name_suffix = self._build_audio_file_name_suffix(target_ext, bitrate)
        return target_ext, file_name_suffix

    def _build_audio_file_name_suffix(self, target_ext, bitrate):
        parts = []
        if target_ext:
            parts.append(str(target_ext).lower())
        if bitrate:
            parts.append(f"{bitrate}kbps")
        if not parts:
            return None
        return f"[{' '.join(parts)}]"

    def _find_selected_video_format(self, selected_id):
        if selected_id is None:
            return None

        selected_id_str = str(selected_id)
        return next(
            (f for f in self.video_formats if str(f.get('format_id')) == selected_id_str),
            None,
        )

    def _build_file_name_suffix(self, selected_format):
        if not selected_format:
            return None

        width = selected_format.get('width')
        height = selected_format.get('height')
        resolution = f"{width}x{height}" if width and height else None

        codec = selected_format.get('vcodec_clean') or selected_format.get('vcodec')
        if codec and codec != 'none':
            codec = codec.split('.')[0]
        else:
            codec = None

        if resolution and codec:
            return f"[{resolution} {codec}]"
        if resolution:
            return f"[{resolution}]"
        if codec:
            return f"[{codec}]"
        return None

    def _apply_subtitle_options(self, ydl_opts, selected_subtitle):
        if selected_subtitle is None:
            return None

        selected_languages = []
        include_auto_subs = self.settings_manager.get_include_auto_subs()

        if selected_subtitle == "__all__":
            all_languages = list(self.subtitle_languages)
            if include_auto_subs:
                all_languages.extend(self.auto_subtitle_languages)
            selected_languages = sorted(set(all_languages))
        elif isinstance(selected_subtitle, tuple):
            _, language_code = selected_subtitle
            selected_languages = [language_code]
        else:
            selected_languages = [selected_subtitle]

        ydl_opts['merge_output_format'] = 'mkv'
        ydl_opts['writesubtitles'] = True
        ydl_opts['embedsubtitles'] = True
        ydl_opts['writeautomaticsub'] = include_auto_subs
        ydl_opts['subtitlesformat'] = 'srt/best'
        ydl_opts['convertsubtitles'] = 'srt'
        ydl_opts['keepvideo'] = True
        ydl_opts['compat_opts'] = ['no-keep-subs']

        postprocessors = ydl_opts.setdefault('postprocessors', [])
        postprocessors.append({'key': 'FFmpegMetadata', 'add_chapters': True})
        postprocessors.append({'key': 'EmbedThumbnail'})
        postprocessors.append({'key': 'FFmpegEmbedSubtitle'})

        ydl_opts['subtitleslangs'] = selected_languages

        return 'mkv'

    def _build_video_download_options(self, ydl_opts):
        selected_id = self.cb_quality.currentData()
        fmt_data = self.cb_format.currentData()
        selected_subtitle = self.cb_subtitles.currentData()

        target_ext = "mp4"
        file_name_suffix = None

        if selected_id and fmt_data:
            target_ext = fmt_data[0]
            selected_format = self._find_selected_video_format(selected_id)

            if selected_format and selected_format.get('acodec') != 'none':
                ydl_opts['format'] = str(selected_id)
            else:
                if target_ext == 'mp4':
                    audio_selector = 'bestaudio[ext=m4a]/bestaudio/best'
                elif target_ext == 'webm':
                    audio_selector = 'bestaudio[ext=webm]/bestaudio/best'
                else:
                    audio_selector = 'bestaudio/best'

                ydl_opts['format'] = f"{selected_id}+{audio_selector}"
                ydl_opts['merge_output_format'] = target_ext

            file_name_suffix = self._build_file_name_suffix(selected_format)
        else:
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
            ydl_opts['merge_output_format'] = 'mp4'

        subtitle_target_ext = self._apply_subtitle_options(ydl_opts, selected_subtitle)
        if subtitle_target_ext:
            target_ext = subtitle_target_ext

        return target_ext, file_name_suffix

    def start_download(self):
        if self.download_worker or self.info_worker:
            return

        if self.queue_manager.count_pending() > 0 and not self._queue_active:
            self.process_queue()
            return

        self._start_download_for_url(self.url_input.text().strip())

    def _start_download_for_url(self, url):
        url = (url or "").strip()
        if not url:
            return

        if self.tray_manager and self.tray_manager.available:
            if self._queue_active:
                self.tray_manager.set_status_queue(self.queue_manager.count_pending())
            else:
                self.tray_manager.set_status_downloading(self._get_active_download_title())

        is_audio = self.rb_audio.isChecked()
        playlist_mode = self.cb_download_playlist.isChecked()

        temp_dir = None
        if not playlist_mode:
            temp_dir = tempfile.mkdtemp(prefix="media_downloader_tmp_")

        ydl_opts = self._build_base_ydl_opts(temp_dir, playlist_mode)

        target_ext = "mp4"
        file_name_suffix = None

        if is_audio:
            target_ext, file_name_suffix = self._build_audio_download_options(ydl_opts)
        else:
            target_ext, file_name_suffix = self._build_video_download_options(ydl_opts)

        logger.info(
            "Download started: url=%s type=%s playlist=%s target_ext=%s folder=%s",
            url,
            "audio" if is_audio else "video",
            playlist_mode,
            target_ext,
            self.download_folder,
        )

        self.btn_download.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_settings.setEnabled(False)
        self.btn_add_queue.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 600; color: #b8c2d1;")
        self.start_status_animation("Starting download")

        self.download_worker = DownloadWorker(
            url,
            ydl_opts,
            temp_dir,
            target_ext,
            self.download_folder,
            file_name_suffix,
            playlist_mode=playlist_mode,
        )
        self.download_worker.progress_signal.connect(self.update_progress)
        self.download_worker.finished_signal.connect(self.on_download_finished)
        self.download_worker.error_signal.connect(self.on_download_error)
        self.download_worker.start()
        self._update_download_button_text()

    def update_progress(self, percent, text):
        self.progress_bar.setValue(int(percent))
        if self._queue_active and self._current_queue_index is not None:
            self.queue_manager.update_progress(self._current_queue_index, percent)
            self.queue_widget.refresh_item(self._current_queue_index)

        if text == "Processing / Converting...":
            self.start_status_animation("Processing / Converting")
            return

        self.stop_status_animation()
        self.lbl_status.setText(text)

    def on_download_finished(self, msg):
        self.stop_status_animation()
        logger.info("Download finished: %s", msg)
        notification_title = self._get_active_download_title()
        if self._queue_active and self._current_queue_index is not None:
            self.queue_manager.update_status(self._current_queue_index, "finished")
            self.queue_manager.update_progress(self._current_queue_index, 100)
            self.queue_widget.refresh_item(self._current_queue_index)
            self._queue_summary["finished"] += 1
            self._current_queue_index = None
            self.lbl_status.setText(f"Queue item finished: {msg}")
        else:
            self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 600; color: #8fbf8f;")
        self.finish_download_ui()
        if self.settings_manager.get_show_notifications() and not self._queue_active:
            QMessageBox.information(self, "Finished", msg)

        if not self._queue_active:
            if self._is_tray_notification_enabled_and_hidden():
                self.tray_manager.notify_download_complete(notification_title)
            if self.tray_manager and self.tray_manager.available:
                self.tray_manager.set_status_idle()

        self.update_system_info()

        if self._queue_active:
            if self.tray_manager and self.tray_manager.available:
                self.tray_manager.set_status_queue(self.queue_manager.count_pending())
            self.process_queue()

    def on_download_error(self, err):
        self.stop_status_animation()
        logger.warning("Download error: %s", err)
        notification_title = self._get_active_download_title()
        if self._queue_active and self._current_queue_index is not None:
            lowered = (err or "").lower()
            is_cancel = "cancel" in lowered
            if is_cancel:
                self.queue_manager.update_status(self._current_queue_index, "cancelled", err)
                self._queue_summary["cancelled"] += 1
            else:
                self.queue_manager.update_status(self._current_queue_index, "error", err)
                self._queue_summary["error"] += 1
            self.queue_widget.refresh_item(self._current_queue_index)
            self._current_queue_index = None
            self.lbl_status.setText(f"Queue item failed: {err}")
        else:
            self.lbl_status.setText(err)
        self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 600; color: #d98787;")

        if self._is_tray_notification_enabled_and_hidden():
            self.tray_manager.notify_download_error(notification_title, err)

        self.finish_download_ui()

        if self._queue_active:
            if self.tray_manager and self.tray_manager.available:
                self.tray_manager.set_status_queue(self.queue_manager.count_pending())
            self.process_queue()
        elif self.tray_manager and self.tray_manager.available:
            self.tray_manager.set_status_idle()

    def finish_download_ui(self):
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(self._queue_active and self.queue_manager.count_pending() > 0)
        self.btn_settings.setEnabled(True)
        self.btn_add_queue.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.download_worker = None
        self.info_worker = None
        self._update_download_button_text()

    def cancel_download(self):
        shift_pressed = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)

        if self._queue_active:
            self._queue_cancel_requested = True
            if shift_pressed:
                self._cancel_all_pending_queue_items()

            if self.download_worker:
                self.download_worker.cancel()
            elif self.info_worker and self.info_worker.isRunning():
                self._mark_current_queue_item_cancelled()
                self.process_queue()
            return

        if self.download_worker:
            self.download_worker.cancel()

    def event(self, event):
        if event.type() == QEvent.Type.WindowActivate:
            QTimer.singleShot(0, self.try_auto_paste_url)
        return super().event(event)

    def try_auto_paste_url(self):
        if not self.settings_manager.get_clipboard_autopaste():
            return

        if self.url_input.text().strip():
            return

        clipboard = QApplication.clipboard()
        clip_text = (clipboard.text() or "").strip()
        if clip_text.startswith("http") or clip_text.startswith("www"):
            self.url_input.setText(clip_text)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.try_auto_paste_url()

    def update_system_info(self):
        if self._yt_dlp_version is None:
            try:
                import yt_dlp.version
                self._yt_dlp_version = yt_dlp.version.__version__
            except Exception:
                self._yt_dlp_version = "unknown"

        if self._app_version is None:
            try:
                version_path = resource_path("VERSION.txt")
                with open(version_path, "r", encoding="utf-8") as f:
                    self._app_version = f.read().strip() or "unknown"
            except Exception:
                self._app_version = "unknown"

        ffmpeg_loc = get_ffmpeg_location()
        if ffmpeg_loc is False:
            logger.info("FFmpeg detection result: missing")
        elif ffmpeg_loc is None:
            logger.info("FFmpeg detection result: available via PATH")
        else:
            logger.info("FFmpeg detection result: %s", ffmpeg_loc)

        disk = get_disk_space(self.download_folder)
        ver = self._yt_dlp_version
        ff_stat = "✅ FFmpeg active" if ffmpeg_loc is not False else "⚠️ FFmpeg missing"
        app_ver = self._app_version
        self.lbl_system_info.setText(f"{ff_stat}  |  ℹ️ yt-dlp v{ver}  |  💾 {disk}  |  🛠️ Version {app_ver}")

    def change_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.download_folder = folder
            self.lbl_folder.setText(folder)
            logger.info("Download folder changed: %s", folder)
            self.update_system_info()

    def open_folder(self):
        if os.path.exists(self.download_folder):
            if platform.system() == "Windows":
                os.startfile(self.download_folder)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", self.download_folder])
            else:
                subprocess.Popen(["xdg-open", self.download_folder])

    def add_to_queue(self):
        url = self.url_input.text().strip()
        if not url:
            return

        mode = "Audio" if self.rb_audio.isChecked() else "Video"
        options = self._capture_queue_item_options()
        index = self.queue_widget.add_item(url, mode, options=options)

        known_title = self._get_known_title_for_url(url)
        if known_title:
            self.queue_manager.update_title(index, known_title)
            self.queue_widget.refresh_item(index)

        self.lbl_status.setText("Added to queue.")
        self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 600; color: #9cc06b;")
        self._update_download_button_text()

    def _normalize_url_for_match(self, url):
        value = str(url or "").strip()
        if value.endswith("/"):
            value = value[:-1]
        return value

    def _get_known_title_for_url(self, url):
        info = self.video_info or {}
        title = str(info.get("title") or "").strip()
        if not title:
            return None

        normalized_url = self._normalize_url_for_match(url)
        candidates = [
            info.get("webpage_url"),
            info.get("original_url"),
            self.url_input.text().strip(),
        ]

        normalized_candidates = {
            self._normalize_url_for_match(candidate)
            for candidate in candidates
            if candidate
        }

        if normalized_url in normalized_candidates:
            return title
        return None

    def on_queue_changed(self):
        self._update_download_button_text()
        if self._queue_active and self.tray_manager and self.tray_manager.available:
            self.tray_manager.set_status_queue(self.queue_manager.count_pending())

    def on_queue_expanded_changed(self, expanded):
        if expanded:
            self.setFixedSize(*self._expanded_size)
        else:
            self.setFixedSize(*self._collapsed_size)

    def on_clear_queue_requested(self):
        total_items = len(self.queue_manager.get_all())
        if total_items == 0:
            return

        reply = QMessageBox.warning(
            self,
            "Clear queue",
            "This will remove all queued items, including unfinished downloads. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if self._queue_active:
            self._queue_active = False
            self._queue_cancel_requested = True
            self._current_queue_index = None
            self._queue_summary = {"finished": 0, "error": 0, "cancelled": 0}

            if self.download_worker:
                self.download_worker.cancel()

        cleared = self.queue_manager.clear_all()
        if cleared:
            self.queue_widget.refresh()
            self.on_queue_changed()
            self.lbl_status.setText("Queue cleared.")
            self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 600; color: #b8c2d1;")
            if self.tray_manager and self.tray_manager.available:
                self.tray_manager.set_status_idle()

    def on_tray_quit_requested(self):
        self._force_app_quit = True
        self._queue_active = False
        self._queue_cancel_requested = True
        if self.download_worker:
            self.download_worker.cancel()
        if self.tray_manager:
            self.tray_manager.shutdown()
        QApplication.quit()

    def closeEvent(self, event):
        tray_available = bool(self.tray_manager and self.tray_manager.available and QSystemTrayIcon.isSystemTrayAvailable())
        minimize_to_tray = self.settings_manager.get_minimize_to_tray()

        if self._force_app_quit:
            if self.tray_manager:
                self.tray_manager.shutdown()
            event.accept()
            return

        if minimize_to_tray and tray_available:
            event.ignore()
            self.hide()
            if not self._tray_close_notice_shown:
                self.tray_manager.tray_icon.showMessage(
                    "Media Downloader",
                    "Media Downloader is still running in the system tray.",
                    QSystemTrayIcon.MessageIcon.Information,
                    4000,
                )
                self._tray_close_notice_shown = True
            return

        self._force_app_quit = True
        if self.tray_manager:
            self.tray_manager.shutdown()
        event.accept()
        QApplication.quit()

    def _cancel_all_pending_queue_items(self):
        for item in self.queue_manager.get_all():
            if item["status"] == "pending":
                item["status"] = "cancelled"
                self._queue_summary["cancelled"] += 1
        self.queue_widget.refresh()

    def _mark_current_queue_item_cancelled(self):
        if self._current_queue_index is None:
            return
        self.queue_manager.update_status(self._current_queue_index, "cancelled", "Cancelled by user")
        self.queue_widget.refresh_item(self._current_queue_index)
        self._queue_summary["cancelled"] += 1
        self._current_queue_index = None
        self._queue_cancel_requested = False

    def process_queue(self):
        if self.download_worker or self.info_worker:
            return

        if not self._queue_active:
            self._queue_active = True
            self._queue_summary = {"finished": 0, "error": 0, "cancelled": 0}

        next_index, item = self.queue_manager.get_next_pending()
        if item is None:
            self._queue_active = False
            self._current_queue_index = None
            self._queue_cancel_requested = False
            done = self._queue_summary["finished"]
            failed = self._queue_summary["error"]
            cancelled = self._queue_summary["cancelled"]
            summary_text = f"Queue finished: {done} completed, {failed} failed, {cancelled} cancelled."
            self.lbl_status.setText(summary_text)
            self.lbl_status.setStyleSheet("font-size: 15px; font-weight: 600; color: #b8c2d1;")
            self.btn_cancel.setEnabled(False)

            if self._is_tray_notification_enabled_and_hidden():
                self.tray_manager.notify_queue_complete(done, failed, cancelled)
            if self.tray_manager and self.tray_manager.available:
                self.tray_manager.set_status_idle()

            self._update_download_button_text()
            return

        self._current_queue_index = next_index
        self._queue_cancel_requested = False
        self.queue_manager.update_status(next_index, "downloading")
        self.queue_manager.update_progress(next_index, 0)
        self.queue_widget.refresh_item(next_index)

        self.url_input.setText(item["url"])
        if item.get("mode", "Video").lower() == "audio":
            self.rb_audio.setChecked(True)
        else:
            self.rb_video.setChecked(True)
        self.update_ui_state()

        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setText("CANCEL (Shift=All)")
        if self.tray_manager and self.tray_manager.available:
            self.tray_manager.set_status_queue(self.queue_manager.count_pending())
        self.start_fetch_info()

    def _update_download_button_text(self):
        has_pending = self.queue_manager.count_pending() > 0
        busy = bool(self.download_worker or self.info_worker)
        if self._queue_active:
            self.btn_download.setText("QUEUE RUNNING")
            self.btn_download.setEnabled(False)
            self.btn_cancel.setText("CANCEL (Shift=All)")
            return

        self.btn_cancel.setText("CANCEL")
        if has_pending:
            self.btn_download.setText("START QUEUE")
        else:
            self.btn_download.setText("DOWNLOAD")

        self.btn_download.setEnabled((not busy) and (has_pending or bool(self.url_input.text().strip())))

    def _capture_queue_item_options(self):
        is_audio = self.rb_audio.isChecked()

        options = {
            "mode": "Audio" if is_audio else "Video",
            "playlist": self.cb_download_playlist.isChecked(),
            "subtitle": self.cb_subtitles.currentData(),
        }

        if is_audio:
            options.update(
                {
                    "audio_format": self.cb_format.currentText(),
                    "audio_bitrate": self.cb_quality.currentData(),
                }
            )
        else:
            options.update(
                {
                    "video_format_data": self.cb_format.currentData(),
                    "video_format_text": self.cb_format.currentText(),
                    "video_fps": self.cb_fps.currentData(),
                    "video_quality_text": self.cb_quality.currentText(),
                }
            )

        return options

    def _apply_queue_item_options(self, item):
        options = item.get("options") or {}

        self.cb_download_playlist.setChecked(bool(options.get("playlist", False)))

        mode = str(options.get("mode") or item.get("mode") or "Video").lower()
        if mode == "audio":
            self.rb_audio.setChecked(True)
        else:
            self.rb_video.setChecked(True)

        self.update_ui_state()

        if self.rb_audio.isChecked():
            target_format = options.get("audio_format")
            if target_format:
                format_index = self.cb_format.findText(str(target_format))
                if format_index >= 0:
                    self.cb_format.setCurrentIndex(format_index)

            target_bitrate = options.get("audio_bitrate")
            if target_bitrate is not None:
                bitrate_index = self.cb_quality.findData(target_bitrate)
                if bitrate_index >= 0:
                    self.cb_quality.setCurrentIndex(bitrate_index)
            return

        target_format_data = options.get("video_format_data")
        target_format_text = options.get("video_format_text")
        format_index = -1

        if target_format_data is not None:
            format_index = self.cb_format.findData(target_format_data)

        if format_index < 0 and target_format_text:
            format_index = self.cb_format.findText(str(target_format_text))

        if format_index >= 0:
            self.cb_format.setCurrentIndex(format_index)

        target_fps = options.get("video_fps")
        if target_fps is not None:
            fps_index = self.cb_fps.findData(target_fps)
            if fps_index >= 0:
                self.cb_fps.setCurrentIndex(fps_index)

        target_quality_text = options.get("video_quality_text")
        if target_quality_text:
            quality_index = self.cb_quality.findText(str(target_quality_text))
            if quality_index >= 0:
                self.cb_quality.setCurrentIndex(quality_index)

        target_subtitle = options.get("subtitle")
        subtitle_index = self.cb_subtitles.findData(target_subtitle)
        if subtitle_index >= 0:
            self.cb_subtitles.setCurrentIndex(subtitle_index)
        else:
            self.cb_subtitles.setCurrentIndex(0)

