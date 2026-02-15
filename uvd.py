import sys
import os
import shutil
import re
import platform
import subprocess
from pathlib import Path

# PyQt6 imports for GUI components
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QLineEdit, QPushButton, QComboBox, QProgressBar, 
                            QFileDialog, QMessageBox, QRadioButton, QButtonGroup, QFrame,
                            QSizePolicy, QCheckBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont

import yt_dlp
import yt_dlp.version

# --- CONFIGURATION ---

# Static configuration for capabilities
AUDIO_FORMATS = {
    'mp3':  {'thumb': True,  'meta': True},
    'm4a':  {'thumb': True,  'meta': True},
    'flac': {'thumb': True,  'meta': True},
    'opus': {'thumb': False, 'meta': True}, 
    'wav':  {'thumb': False, 'meta': True},
}

def resource_path(relative_path):
    """ Get absolute path to resource (works for PyInstaller). """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Cache for FFmpeg location to avoid repeated disk I/O
_CACHED_FFMPEG = None

def get_ffmpeg_location():
    """ 
    Attempt to locate the FFmpeg binary with caching for performance.
    """
    global _CACHED_FFMPEG
    if _CACHED_FFMPEG:
        return _CACHED_FFMPEG

    # 1. Bundled inside PyInstaller temp folder
    if hasattr(sys, '_MEIPASS'):
        bundled = os.path.join(sys._MEIPASS, "ffmpeg.exe")
        if os.path.exists(bundled): 
            _CACHED_FFMPEG = bundled
            return bundled
        
    # 2. Local folder (Development)
    local = os.path.join(os.getcwd(), "ffmpeg.exe")
    if os.path.exists(local): 
        _CACHED_FFMPEG = local
        return local

    # 3. System PATH
    if shutil.which("ffmpeg"): 
        _CACHED_FFMPEG = None # Let yt-dlp use system path
        return None 

    # 4. Common Windows paths
    paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ffmpeg', 'bin', 'ffmpeg.exe')
    ]
    for p in paths:
        if os.path.exists(p): 
            _CACHED_FFMPEG = p
            return p
        
    return False

def format_size(bytes_val):
    """ Helper to convert bytes to human-readable strings. """
    if not bytes_val or bytes_val == 0: return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"

def get_disk_space(path):
    """ Returns a string representing free disk space. """
    try:
        total, used, free = shutil.disk_usage(path)
        return format_size(free) + " free"
    except:
        return "Disk unknown"

# --- BACKGROUND WORKERS ---

class InfoWorker(QThread):
    """ 
    Worker to fetch video metadata. 
    Optimized to ignore playlists for speed.
    """
    finished_signal = pyqtSignal(dict, list)
    error_signal = pyqtSignal(str)

    def __init__(self, url, cookies=None):
        super().__init__()
        self.url = url
        self.cookies = cookies

    def run(self):
        # Optimized options for fast fetching
        ydl_opts = {
            'quiet': True, 
            'no_warnings': True,
            'noplaylist': True, # CRITICAL: Speed up fetch if URL is video+playlist
            'extract_flat': False,
        }
        if self.cookies: ydl_opts['cookiesfrombrowser'] = (self.cookies, )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                formats = info.get('formats', [])
                
                clean_formats = []
                for f in formats:
                    # Strict filtering for usable video streams
                    if f.get('vcodec') != 'none' and f.get('height'):
                        
                        fps = f.get('fps')
                        if fps: f['fps_rounded'] = int(round(fps))
                        else: f['fps_rounded'] = 0
                        
                        codec = f.get('vcodec', 'unknown')
                        f['vcodec_clean'] = codec.split('.')[0]
                        
                        fs = f.get('filesize') or f.get('filesize_approx') or 0
                        f['filesize_str'] = format_size(fs)
                        
                        clean_formats.append(f)
                
                # Sort: Res -> FPS -> Bitrate
                clean_formats.sort(key=lambda x: (x.get('height', 0), x.get('fps_rounded', 0), x.get('tbr', 0)), reverse=True)
                
                self.finished_signal.emit(info, clean_formats)
        except Exception as e:
            self.error_signal.emit(str(e))

class DownloadWorker(QThread):
    """ 
    Worker to handle downloading.
    Optimized for network resilience and parallel fragments.
    """
    progress_signal = pyqtSignal(float, str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, url, opts, temp_dir, target_ext, download_folder):
        super().__init__()
        self.url = url
        self.opts = opts
        self.temp_dir = temp_dir
        self.target_ext = target_ext
        self.download_folder = download_folder
        self.is_cancelled = False

    def run(self):
        # Inject optimization and resilience options
        self.opts.update({
            'progress_hooks': [self.progress_hook],
            'retries': 10,                 # Retry 10 times on network error
            'fragment_retries': 10,        # Retry specific fragments
            'socket_timeout': 15,          # Timeout after 15s of silence
            'concurrent_fragment_downloads': 4, # Parallel download boost
            'file_access_retries': 5,      # Handling file locks
        })

        try:
            with yt_dlp.YoutubeDL(self.opts) as ydl:
                ydl.download([self.url])
            
            if self.is_cancelled:
                self.error_signal.emit("⛔ Cancelled.")
                return

            # Robust file finding logic
            files = [os.path.join(self.temp_dir, f) for f in os.listdir(self.temp_dir) 
                    if os.path.isfile(os.path.join(self.temp_dir, f))]
            
            target = None
            # 1. Exact match
            for f in files:
                if f.endswith(f".{self.target_ext}"):
                    target = f
                    break
            # 2. Fallback (Largest file)
            if not target and files: target = max(files, key=os.path.getsize)

            if target:
                final_path = os.path.join(self.download_folder, os.path.basename(target))
                if os.path.exists(final_path): os.remove(final_path)
                shutil.move(target, final_path)
                self.finished_signal.emit("✅ DONE! File saved.")
            else:
                self.error_signal.emit("Error: File not found.")

        except Exception as e:
            if self.is_cancelled: self.error_signal.emit("⛔ Cancelled.")
            else: self.error_signal.emit(f"Error: {str(e)[:100]}...")
        finally:
            try: shutil.rmtree(self.temp_dir)
            except: pass

    def progress_hook(self, d):
        if self.is_cancelled: raise Exception("Cancelled")
        if d['status'] == 'downloading':
            try:
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                percent = (downloaded / total * 100) if total > 0 else 0
                
                # Clean up ANSI codes
                spd = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_speed_str', 'N/A'))
                
                msg = f"Downloading: {format_size(downloaded)} / {format_size(total)} | {spd}"
                self.progress_signal.emit(percent, msg)
            except: pass
        elif d['status'] == 'finished':
            self.progress_signal.emit(100, "Processing / Converting...")

    def cancel(self):
        self.is_cancelled = True

# --- MAIN APPLICATION WINDOW ---

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Universal Video Downloader")
        self.resize(850, 520)
        
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path): self.setWindowIcon(QIcon(icon_path))
        
        self.download_folder = str(Path.home() / "Downloads")
        self.video_info = {}
        self.video_formats = [] 
        
        self.fetch_timer = QTimer()
        self.fetch_timer.setSingleShot(True)
        self.fetch_timer.timeout.connect(self.start_fetch_info)
        
        self.download_worker = None
        self.info_worker = None

        self.setup_ui()
        self.apply_stylesheet()
        self.update_system_info()
        self.update_ui_state()

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
        
        settings_layout.addSpacing(15)

        self.cb_subtitles = QCheckBox("Subtitles")
        self.cb_subtitles.setChecked(False)
        self.cb_subtitles.setToolTip("Download and embed subtitles (if available)")
        settings_layout.addWidget(self.cb_subtitles)

        settings_layout.addStretch()

        settings_layout.addWidget(QLabel("Cookies:"))
        self.cb_cookies = QComboBox()
        self.cb_cookies.addItems(["None", "Chrome", "Edge", "Firefox", "Opera"])
        self.cb_cookies.setFixedWidth(90)
        settings_layout.addWidget(self.cb_cookies)

        layout.addWidget(settings_frame)

        # Quality
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Quality:"))
        self.cb_quality = QComboBox()
        self.cb_quality.setEnabled(False)
        quality_layout.addWidget(self.cb_quality, 1)
        layout.addLayout(quality_layout)

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
        if not url or (not url.startswith("http") and "www" not in url): return
        
        self.lbl_status.setText("Fetching information...")
        self.lbl_status.setStyleSheet("") 
        self.fetch_btn.setEnabled(False)
        self.btn_download.setEnabled(False)
        
        cookies_val = self.cb_cookies.currentText().lower()
        cookies = cookies_val if cookies_val != "none" else None

        self.info_worker = InfoWorker(url, cookies)
        self.info_worker.finished_signal.connect(self.on_info_fetched)
        self.info_worker.error_signal.connect(self.on_info_error)
        self.info_worker.start()

    def on_info_fetched(self, info, formats):
        self.video_info = info
        self.video_formats = formats
        self.lbl_status.setText(f"Loaded: {info.get('title')}")
        self.fetch_btn.setEnabled(True)
        self.update_ui_state()

    def on_info_error(self, err):
        self.lbl_status.setText(f"Error: {err[:50]}...")
        self.fetch_btn.setEnabled(True)

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
            self.cb_subtitles.setEnabled(False)
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
            self.cb_subtitles.setEnabled(True)
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
        if not selected_data: return

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

    def on_fps_changed(self):
        self.cb_quality.blockSignals(True)
        self.cb_quality.clear()
        
        selected_fmt_data = self.cb_format.currentData()
        selected_fps = self.cb_fps.currentData()
        
        if not selected_fmt_data or selected_fps is None: return
        
        sel_ext, sel_codec = selected_fmt_data
        candidates = [f for f in self.video_formats 
                    if f.get('ext') == sel_ext and f.get('vcodec_clean') == sel_codec]
        
        res_groups = {}
        for f in candidates:
            h = f.get('height', 0)
            if h not in res_groups: res_groups[h] = []
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
            "<li><b>Type (Video/Audio):</b> Switch between downloading video or extracting audio only.</li>"
            "<li><b>Format:</b> Select specific video container and codec (e.g., MP4 with AVC1).</li>"
            "<li><b>FPS:</b> Preferred framerate. If the specific FPS isn't available, the best alternative is selected.</li>"
            "<li><b>Subtitles:</b> If checked, attempts to download and embed subtitles (EN, CZ, SK, etc.).</li>"
            "<li><b>Cookies:</b> Borrow cookies from your browser to access age-restricted or premium content.</li>"
            "<li><b>Quality:</b> Final selection for video resolution or audio bitrate.</li>"
            "</ul>"
            "<p><i>Note: FFmpeg is required for merging video and audio streams.</i></p>"
        )
        QMessageBox.information(self, "App Help", help_text)

    def start_download(self):
        url = self.url_input.text().strip()
        if not url: return

        is_audio = self.rb_audio.isChecked()
        cookies_val = self.cb_cookies.currentText().lower()
        cookies = cookies_val if cookies_val != "none" else None
        download_subs = self.cb_subtitles.isChecked()
        
        temp_dir = os.path.join(self.download_folder, "temp_download")
        if not os.path.exists(temp_dir): os.makedirs(temp_dir, exist_ok=True)

        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'paths': {'home': temp_dir},
            'quiet': True, 
            'no_warnings': True,
            'overwrites': True,
        }
        
        loc_ffmpeg = get_ffmpeg_location()
        if loc_ffmpeg: ydl_opts['ffmpeg_location'] = loc_ffmpeg
        if cookies: ydl_opts['cookiesfrombrowser'] = (cookies, )

        target_ext = "mp4" 

        if is_audio:
            target_ext = self.cb_format.currentText()
            bitrate = self.cb_quality.currentData()
            
            ydl_opts['format'] = 'bestaudio/best'
            pps = [{'key': 'FFmpegExtractAudio', 'preferredcodec': target_ext, 'preferredquality': bitrate}]
            
            conf = AUDIO_FORMATS.get(target_ext, {})
            if conf.get('thumb'): pps.append({'key': 'EmbedThumbnail'})
            if conf.get('meta'): pps.append({'key': 'FFmpegMetadata'})
            
            ydl_opts['postprocessors'] = pps
        else:
            selected_id = self.cb_quality.currentData()
            fmt_data = self.cb_format.currentData()
            
            if selected_id and fmt_data:
                target_ext = fmt_data[0]
                
                ydl_opts['format'] = f"{selected_id}+bestaudio/best"
                ydl_opts['merge_output_format'] = target_ext
                
                pps = []
                pps.append({'key': 'FFmpegMetadata', 'add_chapters': True})
                pps.append({'key': 'EmbedThumbnail'})
                
                pps_args = {}
                if target_ext == 'mp4':
                    pps_args = {'merger': ['-c:v', 'copy', '-c:a', 'aac']}
                
                ydl_opts['postprocessors'] = pps
                ydl_opts['postprocessor_args'] = pps_args
                
                if download_subs:
                    ydl_opts['writesubtitles'] = True
                    ydl_opts['embedsubtitles'] = True
                    ydl_opts['subtitleslangs'] = ['en.*', 'cs', 'sk', 'de', 'es'] 
                else:
                    ydl_opts['writesubtitles'] = False
            else:
                ydl_opts['format'] = 'bestvideo+bestaudio/best'
                ydl_opts['merge_output_format'] = 'mp4'

        self.btn_download.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Starting download...")
        self.lbl_status.setStyleSheet("") 

        self.download_worker = DownloadWorker(url, ydl_opts, temp_dir, target_ext, self.download_folder)
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
        if self.download_worker: self.download_worker.cancel()

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
            if platform.system() == "Windows": os.startfile(self.download_folder)
            elif platform.system() == "Darwin": subprocess.Popen(["open", self.download_folder])
            else: subprocess.Popen(["xdg-open", self.download_folder])

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())