import os
import platform
import subprocess
import tempfile
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QButtonGroup,
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
    QVBoxLayout,
    QWidget,
)

import yt_dlp.version

from .config import AUDIO_FORMATS, LANGUAGE_NAMES
from .utils import get_disk_space, get_ffmpeg_location, resource_path
from .workers import DownloadWorker, InfoWorker


# This file defines the main window of the Universal Video Downloader application.
# It contains the UI layout, event handlers, and logic for fetching video information and downloading videos.


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Universal Video Downloader")
        self.resize(850, 520)

        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.download_folder = str(Path.home() / "Downloads")
        self.video_info = {}
        self.video_formats = []
        self.subtitle_languages = []

        self.fetch_timer = QTimer()
        self.fetch_timer.setSingleShot(True)
        self.fetch_timer.timeout.connect(self.start_fetch_info)

        self.download_worker = None
        self.info_worker = None

        self.setup_ui()
        self.apply_stylesheet()
        self.update_system_info()
        self.update_ui_state()
        self.update_output_indicator()

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_layout = QHBoxLayout()
        title_lbl = QLabel("Universal Video Downloader")
        title_lbl.setStyleSheet("font-size: 24px; font-weight: bold; color: #64b5f6;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_help = QPushButton("?")
        self.btn_help.setFixedSize(30, 30)
        self.btn_help.clicked.connect(self.show_app_help)

        header_layout.addStretch()
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_help)
        layout.addLayout(header_layout)

        # Input
        url_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste link (URL) - Ctrl+V")
        self.url_input.setMinimumHeight(40)
        self.url_input.textChanged.connect(self.on_url_change)

        self.fetch_btn = QPushButton("Fetch")
        self.fetch_btn.setMinimumHeight(40)
        self.fetch_btn.setFixedWidth(100)
        self.fetch_btn.clicked.connect(self.start_fetch_info)

        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.fetch_btn)
        layout.addLayout(url_layout)

        # Settings
        settings_frame = QFrame()
        settings_frame.setObjectName("SettingsFrame")
        settings_layout = QHBoxLayout(settings_frame)
        settings_layout.setContentsMargins(10, 10, 10, 10)

        self.rb_group = QButtonGroup()
        self.rb_video = QRadioButton("Video")
        self.rb_audio = QRadioButton("Audio")
        self.rb_video.setChecked(True)
        self.rb_group.addButton(self.rb_video)
        self.rb_group.addButton(self.rb_audio)
        self.rb_video.toggled.connect(self.update_ui_state)

        settings_layout.addWidget(QLabel("Type:"))
        settings_layout.addWidget(self.rb_video)
        settings_layout.addWidget(self.rb_audio)
        settings_layout.addSpacing(15)

        self.lbl_format = QLabel("Format:")
        settings_layout.addWidget(self.lbl_format)
        self.cb_format = QComboBox()
        self.cb_format.setFixedWidth(130)
        self.cb_format.currentIndexChanged.connect(self.on_format_changed)
        settings_layout.addWidget(self.cb_format)

        self.lbl_fps = QLabel("FPS:")
        settings_layout.addWidget(self.lbl_fps)
        self.cb_fps = QComboBox()
        self.cb_fps.setFixedWidth(60)
        self.cb_fps.currentIndexChanged.connect(self.on_fps_changed)
        settings_layout.addWidget(self.cb_fps)

        self.lbl_subtitles = QLabel("Subtitles:")
        settings_layout.addWidget(self.lbl_subtitles)
        self.cb_subtitles = QComboBox()
        self.cb_subtitles.setFixedWidth(150)
        self.cb_subtitles.currentIndexChanged.connect(self.update_output_indicator)
        settings_layout.addWidget(self.cb_subtitles)
        self.set_subtitle_options([])

        settings_layout.addSpacing(15)

        settings_layout.addStretch()

        layout.addWidget(settings_frame)

        # Quality
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Quality:"))
        self.cb_quality = QComboBox()
        self.cb_quality.setEnabled(False)
        quality_layout.addWidget(self.cb_quality, 1)
        layout.addLayout(quality_layout)

        self.lbl_output_indicator = QLabel("Output file: -")
        self.lbl_output_indicator.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.lbl_output_indicator.setStyleSheet("color: #777; font-size: 11px;")
        layout.addWidget(self.lbl_output_indicator)

        # Folder
        folder_layout = QHBoxLayout()
        self.btn_open_folder = QPushButton("📂 Open")
        self.btn_open_folder.clicked.connect(self.open_folder)
        self.lbl_folder = QLineEdit(self.download_folder)
        self.lbl_folder.setReadOnly(True)
        self.btn_change_folder = QPushButton("Change")
        self.btn_change_folder.clicked.connect(self.change_folder)
        folder_layout.addWidget(self.btn_open_folder)
        folder_layout.addWidget(self.lbl_folder)
        folder_layout.addWidget(self.btn_change_folder)
        layout.addLayout(folder_layout)

        # Status
        self.lbl_system_info = QLabel("Loading info...")
        self.lbl_system_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_system_info.setStyleSheet("color: #777; font-size: 11px;")
        layout.addWidget(self.lbl_system_info)

        self.lbl_status = QLabel("Ready")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self.btn_download = QPushButton("DOWNLOAD")
        self.btn_download.setMinimumHeight(50)
        self.btn_download.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; font-size: 14px; border-radius: 5px;")
        self.btn_download.clicked.connect(self.start_download)
        self.btn_download.setEnabled(False)

        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.setMinimumHeight(50)
        self.btn_cancel.setStyleSheet("background-color: #c62828; color: white; font-weight: bold; font-size: 14px; border-radius: 5px;")
        self.btn_cancel.clicked.connect(self.cancel_download)
        self.btn_cancel.setEnabled(False)

        btn_layout.addWidget(self.btn_download, 3)
        btn_layout.addWidget(self.btn_cancel, 1)
        layout.addLayout(btn_layout)

    def apply_stylesheet(self):
        is_light_mode = self.palette().color(self.backgroundRole()).lightness() > 128

        if is_light_mode:
            # Light mode colors
            bg_color = "#f5f5f5"
            text_color = "#000000"
            border_color = "#cccccc"
            input_bg = "#ffffff"
            btn_bg = "#e1e1e1"
            btn_hover = "#d4d4d4"
            btn_text = "#000000"
        else:
            # Dark mode colors
            bg_color = "#2b2b2b"
            text_color = "#ffffff"
            border_color = "#555"
            input_bg = "#3a3a3a"
            btn_bg = "#444444"
            btn_hover = "#555555"
            btn_text = "#ffffff"

        stylesheet = f"""
            QMainWindow {{ background-color: {bg_color}; }}
            QWidget {{ color: {text_color}; font-family: 'Segoe UI', sans-serif; font-size: 13px; }}
            QMessageBox {{ background-color: {bg_color}; }}
            QMessageBox QLabel {{ color: {text_color}; }}
            QLineEdit {{ background-color: {input_bg}; border: 1px solid {border_color}; border-radius: 4px; padding: 5px; color: {text_color}; }}
            QComboBox {{ background-color: {input_bg}; border: 1px solid {border_color}; border-radius: 4px; padding: 5px; color: {text_color}; }}
            QComboBox::drop-down {{ border: 0px; }}
            QPushButton {{
                background-color: {btn_bg};
                color: {btn_text};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 5px;
                }}
            QPushButton:hover {{background-color: {btn_hover}; }}
            QPushButton:disabled {{background-color: {input_bg}; color: {border_color}; }}
            QCheckBox {{ spacing: 8px; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {border_color}; border-radius: 3px; background: {input_bg}; }}
            QCheckBox::indicator:checked {{ background-color: #64b5f6; border-color: #64b5f6; }}
            QProgressBar {{ border: 1px solid {border_color}; border-radius: 4px; text-align: center; background-color: {input_bg}; }}
            QProgressBar::chunk {{ background-color: #1976d2; border-radius: 3px; }}
            QFrame#SettingsFrame {{ background-color: {bg_color}; border-radius: 8px; padding: 5px; }}
        """
        self.setStyleSheet(stylesheet)

    def on_url_change(self):
        self.fetch_timer.start(350)

    def start_fetch_info(self):
        url = self.url_input.text().strip()
        if not url or (not url.startswith("http") and "www" not in url):
            return

        self.lbl_status.setText("Fetching information...")
        self.lbl_status.setStyleSheet("")
        self.fetch_btn.setEnabled(False)
        self.btn_download.setEnabled(False)

        self.info_worker = InfoWorker(url)
        self.info_worker.finished_signal.connect(self.on_info_fetched)
        self.info_worker.error_signal.connect(self.on_info_error)
        self.info_worker.start()

    def on_info_fetched(self, info, formats, subtitle_languages):
        self.video_info = info
        self.video_formats = formats
        self.subtitle_languages = subtitle_languages
        self.set_subtitle_options(subtitle_languages)
        self.lbl_status.setText(f"Loaded: {info.get('title')}")
        self.fetch_btn.setEnabled(True)
        self.update_ui_state()

    def on_info_error(self, err):
        self.lbl_status.setText(f"Error: {err[:50]}...")
        self.fetch_btn.setEnabled(True)
        self.subtitle_languages = []
        self.set_subtitle_options([])

    def set_subtitle_options(self, subtitle_languages):
        self.cb_subtitles.blockSignals(True)
        self.cb_subtitles.clear()
        self.cb_subtitles.addItem("None", None)

        if subtitle_languages:
            self.cb_subtitles.addItem("All available", "__all__")
            for lang in subtitle_languages:
                self.cb_subtitles.addItem(self.get_language_display_name(lang), lang)

        self.cb_subtitles.blockSignals(False)
        self.update_output_indicator()

    def get_language_display_name(self, language_code):
        base_code = language_code.lower().split("-")[0].split("_")[0]
        language_name = LANGUAGE_NAMES.get(base_code)

        if language_name:
            return f"{language_name} ({language_code})"
        return language_code.upper()

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
            self.lbl_output_indicator.setText(f"Output file: .{audio_ext}")
            self.lbl_output_indicator.setStyleSheet("color: #777; font-size: 11px;")
            return

        if self.cb_subtitles.currentData() is not None:
            self.lbl_output_indicator.setText("Output file: .mkv (subtitles selected)")
            self.lbl_output_indicator.setStyleSheet("color: #64b5f6; font-size: 11px;")
            return

        fmt_data = self.cb_format.currentData()
        video_ext = fmt_data[0] if fmt_data else "mp4"
        self.lbl_output_indicator.setText(f"Output file: .{video_ext}")
        self.lbl_output_indicator.setStyleSheet("color: #777; font-size: 11px;")

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
            "<h3>App Features Guide</h3>"
            "<ul>"
            "<li><b>Fetch:</b> Retrieving video metadata from the provided URL.</li>"
            "<li><b>Type (Video/Audio):</b> Choose full video download or audio extraction only.</li>"
            "<li><b>Format:</b> Select preferred video codec/container or audio format.</li>"
            "<li><b>FPS:</b> Choose framerate for video mode; quality list adapts to your selection.</li>"
            "<li><b>Subtitles:</b> Embeds subtitles into the video (None, one language, or All available).</li>"
            "<li><b>Quality:</b> Choose resolution (video) or bitrate (audio).</li>"
            "<li><b>Output file:</b> Shows final extension. If subtitles are selected in video mode, output changes to <b>.mkv</b>.</li>"
            "<li><b>Filename suffix:</b> Video files include selected resolution and codec at the end (for example [1920x1080 av01]).</li>"
            "</ul>"
            "<p><i>Note: FFmpeg is recommended for best results and required for some post-processing actions.</i></p>"
        )
        QMessageBox.information(self, "App Help", help_text)

    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            return

        is_audio = self.rb_audio.isChecked()
        file_name_suffix = None

        temp_dir = tempfile.mkdtemp(prefix="uvd_tmp_")

        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'paths': {'home': temp_dir},
            'quiet': True,
            'no_warnings': True,
            'overwrites': True,
        }

        loc_ffmpeg = get_ffmpeg_location()
        if loc_ffmpeg:
            ydl_opts['ffmpeg_location'] = loc_ffmpeg

        target_ext = "mp4"

        if is_audio:
            target_ext = self.cb_format.currentText()
            bitrate = self.cb_quality.currentData()

            ydl_opts['format'] = 'bestaudio/best'
            pps = [{'key': 'FFmpegExtractAudio', 'preferredcodec': target_ext, 'preferredquality': bitrate}]

            conf = AUDIO_FORMATS.get(target_ext, {})
            if conf.get('thumb'):
                pps.append({'key': 'EmbedThumbnail'})
            if conf.get('meta'):
                pps.append({'key': 'FFmpegMetadata'})

            ydl_opts['postprocessors'] = pps
        else:
            selected_id = self.cb_quality.currentData()
            fmt_data = self.cb_format.currentData()
            selected_subtitle = self.cb_subtitles.currentData()

            if selected_id and fmt_data:
                target_ext = fmt_data[0]
                selected_format = next(
                    (f for f in self.video_formats if str(f.get('format_id')) == str(selected_id)),
                    None,
                )

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

                if selected_format:
                    width = selected_format.get('width')
                    height = selected_format.get('height')
                    resolution = f"{width}x{height}" if width and height else None

                    codec = selected_format.get('vcodec_clean') or selected_format.get('vcodec')
                    if codec and codec != 'none':
                        codec = codec.split('.')[0]
                    else:
                        codec = None

                    if resolution and codec:
                        file_name_suffix = f"[{resolution} {codec}]"
                    elif resolution:
                        file_name_suffix = f"[{resolution}]"
                    elif codec:
                        file_name_suffix = f"[{codec}]"
            else:
                ydl_opts['format'] = 'bestvideo+bestaudio/best'
                ydl_opts['merge_output_format'] = 'mp4'

            if selected_subtitle is not None:
                target_ext = 'mkv'
                ydl_opts['merge_output_format'] = 'mkv'
                ydl_opts['writesubtitles'] = True
                ydl_opts['embedsubtitles'] = True
                ydl_opts['writeautomaticsub'] = False
                ydl_opts['subtitlesformat'] = 'srt/best'
                ydl_opts['convertsubtitles'] = 'srt'
                ydl_opts['keepvideo'] = True
                ydl_opts['compat_opts'] = ['no-keep-subs']

                postprocessors = ydl_opts.setdefault('postprocessors', [])
                postprocessors.append({'key': 'FFmpegMetadata', 'add_chapters': True})
                postprocessors.append({'key': 'EmbedThumbnail'})
                postprocessors.append({'key': 'FFmpegEmbedSubtitle'})

                if selected_subtitle == "__all__":
                    ydl_opts['subtitleslangs'] = self.subtitle_languages
                else:
                    ydl_opts['subtitleslangs'] = [selected_subtitle]

        self.btn_download.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Starting download...")
        self.lbl_status.setStyleSheet("")

        self.download_worker = DownloadWorker(url, ydl_opts, temp_dir, target_ext, self.download_folder, file_name_suffix)
        self.download_worker.progress_signal.connect(self.update_progress)
        self.download_worker.finished_signal.connect(self.on_download_finished)
        self.download_worker.error_signal.connect(self.on_download_error)
        self.download_worker.start()

    def update_progress(self, percent, text):
        self.progress_bar.setValue(int(percent))
        self.lbl_status.setText(text)

    def on_download_finished(self, msg):
        self.lbl_status.setText(msg)
        self.lbl_status.setStyleSheet("color: #4caf50;")
        self.finish_download_ui()
        QMessageBox.information(self, "Finished", msg)
        self.update_system_info()

    def on_download_error(self, err):
        self.lbl_status.setText(err)
        self.lbl_status.setStyleSheet("color: #f44336;")
        self.finish_download_ui()

    def finish_download_ui(self):
        self.btn_download.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(False)

    def cancel_download(self):
        if self.download_worker:
            self.download_worker.cancel()

    def update_system_info(self):
        ffmpeg_loc = get_ffmpeg_location()
        disk = get_disk_space(self.download_folder)
        ver = yt_dlp.version.__version__
        ff_stat = "✅ FFmpeg active" if ffmpeg_loc else "⚠️ FFmpeg missing"
        self.lbl_system_info.setText(f"{ff_stat}  |  ℹ️ yt-dlp v{ver}  |  💾 {disk}")

    def change_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.download_folder = folder
            self.lbl_folder.setText(folder)
            self.update_system_info()

    def open_folder(self):
        if os.path.exists(self.download_folder):
            if platform.system() == "Windows":
                os.startfile(self.download_folder)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", self.download_folder])
            else:
                subprocess.Popen(["xdg-open", self.download_folder])
