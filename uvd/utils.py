import os
import shutil
import sys

# Utility functions for UVD, including FFmpeg location and size formatting.

# Cache for FFmpeg location to avoid repeated disk I/O
_CACHED_FFMPEG = None

# Resource paths for PyInstaller
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# FFmpeg location logic
def get_ffmpeg_location():
    global _CACHED_FFMPEG
    if _CACHED_FFMPEG:
        return _CACHED_FFMPEG

    if hasattr(sys, '_MEIPASS'):
        bundled = os.path.join(sys._MEIPASS, "ffmpeg.exe")
        if os.path.exists(bundled):
            _CACHED_FFMPEG = bundled
            return bundled

    local = os.path.join(os.getcwd(), "ffmpeg.exe")
    if os.path.exists(local):
        _CACHED_FFMPEG = local
        return local

    if shutil.which("ffmpeg"):
        _CACHED_FFMPEG = None
        return None

    paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'ffmpeg', 'bin', 'ffmpeg.exe')
    ]
    for p in paths:
        if os.path.exists(p):
            _CACHED_FFMPEG = p
            return p

    return False

# Function to format byte sizes into human-readable strings
def format_size(bytes_val):
    if not bytes_val or bytes_val == 0:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"

# Function to get free disk space for a given path
def get_disk_space(path):
    try:
        total, used, free = shutil.disk_usage(path)
        return format_size(free) + " free"
    except Exception:
        return "Disk unknown"
