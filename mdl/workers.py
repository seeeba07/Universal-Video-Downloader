import os
import re
import shutil
import sys
import time

from PyQt6.QtCore import QThread, pyqtSignal

from .logger import logger
from .utils import format_size


# Worker threads for fetching video info and downloading, optimized for performance and resilience.


# InfoWorker: Fetches video info with optimized yt-dlp options for speed.
class InfoWorker(QThread):
    finished_signal = pyqtSignal(dict, list, list, list)
    error_signal = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        import yt_dlp

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'extract_flat': False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                formats = info.get('formats', [])

                clean_formats = []
                for f in formats:
                    if (
                        f.get('vcodec') != 'none'
                        and f.get('height')
                    ):

                        fps = f.get('fps')
                        if fps:
                            f['fps_rounded'] = int(round(fps))
                        else:
                            f['fps_rounded'] = 0

                        codec = f.get('vcodec', 'unknown')
                        f['vcodec_clean'] = codec.split('.')[0]

                        fs = f.get('filesize') or f.get('filesize_approx') or 0
                        f['filesize_str'] = format_size(fs)

                        clean_formats.append(f)

                clean_formats.sort(
                    key=lambda x: (x.get('height', 0), x.get('fps_rounded', 0), x.get('tbr', 0)),
                    reverse=True,
                )

                manual_subtitles = info.get('subtitles', {}) or {}
                subtitle_languages = sorted([
                    lang for lang, entries in manual_subtitles.items()
                    if entries
                ])

                automatic_subtitles = info.get('automatic_captions', {}) or {}
                auto_subtitle_languages = sorted([
                    lang for lang, entries in automatic_subtitles.items()
                    if entries
                ])

                self.finished_signal.emit(info, clean_formats, subtitle_languages, auto_subtitle_languages)
        except Exception as e:
            logger.error("Failed to fetch media info for URL: %s", self.url, exc_info=True)
            self.error_signal.emit(str(e))

# DownloadWorker: Handles the download process with robust error handling and progress reporting.
# It uses yt-dlp's hooks and retries to ensure a smooth experience even on unstable networks.
class DownloadWorker(QThread):
    progress_signal = pyqtSignal(float, str)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, url, opts, temp_dir, target_ext, download_folder, file_name_suffix=None, playlist_mode=False):
        super().__init__()
        self.url = url
        self.opts = opts
        self.temp_dir = temp_dir
        self.target_ext = target_ext
        self.download_folder = download_folder
        self.file_name_suffix = file_name_suffix
        self.playlist_mode = playlist_mode
        self.is_cancelled = False
        self._last_progress_emit_time = 0.0
        self._last_progress_percent = -1.0
        self._started_at = time.time()

    def _safe_suffix(self):
        if not self.file_name_suffix:
            return ""
        return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', self.file_name_suffix).strip().rstrip('.')

    def _apply_suffix_to_file(self, file_path):
        if not self.file_name_suffix or not file_path:
            return
        if not os.path.isfile(file_path):
            return

        base_name, ext = os.path.splitext(os.path.basename(file_path))
        safe_suffix = self._safe_suffix()
        if not safe_suffix or base_name.endswith(safe_suffix):
            return

        renamed_file_name = f"{base_name} {safe_suffix}{ext}"
        renamed_path = os.path.join(os.path.dirname(file_path), renamed_file_name)
        if os.path.exists(renamed_path):
            os.remove(renamed_path)
        os.replace(file_path, renamed_path)

    def _apply_suffix_to_recent_playlist_files(self):
        if not self.file_name_suffix or not self.playlist_mode:
            return

        expected_ext = f".{str(self.target_ext or '').lower().lstrip('.')}"
        if expected_ext == ".":
            return

        cutoff = self._started_at - 2.0
        for root, _, files in os.walk(self.download_folder):
            for name in files:
                file_path = os.path.join(root, name)
                _, ext = os.path.splitext(name)
                if ext.lower() != expected_ext:
                    continue
                try:
                    if os.path.getmtime(file_path) < cutoff:
                        continue
                except OSError:
                    continue
                self._apply_suffix_to_file(file_path)

    def run(self):
        import yt_dlp

        self.opts.update({
            'progress_hooks': [self.progress_hook],
            'retries': 10,
            'fragment_retries': 10,
            'socket_timeout': 15,
            'concurrent_fragment_downloads': 4,
            'file_access_retries': 5,
        })

        try:
            with yt_dlp.YoutubeDL(self.opts) as ydl:
                ydl.download([self.url])

            if self.is_cancelled:
                logger.info("Download cancelled by user: %s", self.url)
                self.error_signal.emit("⛔ Cancelled.")
                return

            if self.playlist_mode:
                self._apply_suffix_to_recent_playlist_files()
                self.finished_signal.emit("DONE! Playlist saved.")
                return

            target = None
            largest_file = None
            largest_size = -1

            if not self.temp_dir or not os.path.isdir(self.temp_dir):
                self.error_signal.emit("Error: Temporary folder missing.")
                return

            with os.scandir(self.temp_dir) as entries:
                for entry in entries:
                    if not entry.is_file():
                        continue

                    path = entry.path
                    if path.endswith(f".{self.target_ext}"):
                        target = path
                        break

                    try:
                        size = entry.stat().st_size
                    except OSError:
                        continue

                    if size > largest_size:
                        largest_size = size
                        largest_file = path

            if not target:
                target = largest_file

            if target:
                final_path = os.path.join(self.download_folder, os.path.basename(target))
                if os.path.exists(final_path):
                    os.remove(final_path)
                shutil.move(target, final_path)

                if self.file_name_suffix:
                    self._apply_suffix_to_file(final_path)

                self.finished_signal.emit("DONE! File saved.")
            else:
                self.error_signal.emit("Error: File not found.")

        except Exception as e:
            if self.is_cancelled:
                logger.info("Download cancelled during processing: %s", self.url)
                self.error_signal.emit("Cancelled.")
            else:
                logger.error("Download failed for URL: %s", self.url, exc_info=True)
                self.error_signal.emit(f"Error: {str(e)[:100]}...")
        finally:
            try:
                if self.temp_dir and os.path.isdir(self.temp_dir):
                    shutil.rmtree(self.temp_dir)
            except Exception:
                pass

    def progress_hook(self, d):
        if self.is_cancelled:
            raise Exception("Cancelled")
        status = d.get('status')
        if status == 'downloading':
            try:
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                percent = (downloaded / total * 100) if total > 0 else 0

                now = time.monotonic()
                should_emit = (
                    self._last_progress_emit_time == 0.0
                    or (now - self._last_progress_emit_time) >= 0.25
                    or abs(percent - self._last_progress_percent) >= 0.5
                    or (total > 0 and downloaded >= total)
                )
                if not should_emit:
                    return

                self._last_progress_emit_time = now
                self._last_progress_percent = percent

                # Clean up ANSI codes
                spd = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_speed_str', 'N/A'))
                eta = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_eta_str', ''))
                eta = eta.strip() or 'N/A'

                msg = f"Downloading: {format_size(downloaded)} / {format_size(total)} | {spd} | ETA: {eta}"
                self.progress_signal.emit(percent, msg)
            except Exception:
                logger.debug("Suppressed exception in progress hook while emitting progress.", exc_info=True)
        elif status == 'finished':
            self.progress_signal.emit(100, "Processing / Converting...")

    def cancel(self):
        self.is_cancelled = True


class UpdateWorker(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def run(self):
        import importlib
        import subprocess

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                capture_output=True,
                text=True,
            )

            combined_output = f"{result.stdout or ''}\n{result.stderr or ''}"

            if result.returncode != 0:
                err_output = (combined_output or "Unknown update error").strip()
                self.error_signal.emit(err_output)
                return

            import yt_dlp.version as ytdlp_version

            importlib.reload(ytdlp_version)
            new_version = ytdlp_version.__version__

            normalized_output = combined_output.lower()
            already_latest = "requirement already satisfied" in normalized_output or "already up-to-date" in normalized_output

            if already_latest:
                self.finished_signal.emit(f"yt-dlp is already up to date (version {new_version}).")
            else:
                self.finished_signal.emit(f"yt-dlp updated successfully to version {new_version}.")
        except Exception as e:
            self.error_signal.emit(str(e))
