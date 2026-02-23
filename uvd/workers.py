import os
import re
import shutil

from PyQt6.QtCore import QThread, pyqtSignal

import yt_dlp

from .utils import format_size


# Worker threads for fetching video info and downloading, optimized for performance and resilience.


# InfoWorker: Fetches video info with optimized yt-dlp options for speed.
class InfoWorker(QThread):
    finished_signal = pyqtSignal(dict, list)
    error_signal = pyqtSignal(str)

    def __init__(self, url, cookies=None):
        super().__init__()
        self.url = url
        self.cookies = cookies

    def run(self):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'extract_flat': False,
        }
        if self.cookies:
            ydl_opts['cookiesfrombrowser'] = (self.cookies,)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
                formats = info.get('formats', [])

                clean_formats = []
                for f in formats:
                    if f.get('vcodec') != 'none' and f.get('height'):

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

                self.finished_signal.emit(info, clean_formats)
        except Exception as e:
            self.error_signal.emit(str(e))

# DownloadWorker: Handles the download process with robust error handling and progress reporting.
# It uses yt-dlp's hooks and retries to ensure a smooth experience even on unstable networks.
class DownloadWorker(QThread):
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
                self.error_signal.emit("⛔ Cancelled.")
                return

            files = [
                os.path.join(self.temp_dir, f)
                for f in os.listdir(self.temp_dir)
                if os.path.isfile(os.path.join(self.temp_dir, f))
            ]

            target = None
            for f in files:
                if f.endswith(f".{self.target_ext}"):
                    target = f
                    break
            if not target and files:
                target = max(files, key=os.path.getsize)

            if target:
                final_path = os.path.join(self.download_folder, os.path.basename(target))
                if os.path.exists(final_path):
                    os.remove(final_path)
                shutil.move(target, final_path)
                self.finished_signal.emit("✅ DONE! File saved.")
            else:
                self.error_signal.emit("Error: File not found.")

        except Exception as e:
            if self.is_cancelled:
                self.error_signal.emit("⛔ Cancelled.")
            else:
                self.error_signal.emit(f"Error: {str(e)[:100]}...")
        finally:
            try:
                shutil.rmtree(self.temp_dir)
            except Exception:
                pass

    def progress_hook(self, d):
        if self.is_cancelled:
            raise Exception("Cancelled")
        if d['status'] == 'downloading':
            try:
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes', 0)
                percent = (downloaded / total * 100) if total > 0 else 0

                # Clean up ANSI codes
                spd = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_speed_str', 'N/A'))

                msg = f"Downloading: {format_size(downloaded)} / {format_size(total)} | {spd}"
                self.progress_signal.emit(percent, msg)
            except Exception:
                pass
        elif d['status'] == 'finished':
            self.progress_signal.emit(100, "Processing / Converting...")

    def cancel(self):
        self.is_cancelled = True
