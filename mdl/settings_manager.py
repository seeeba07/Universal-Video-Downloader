from pathlib import Path

from PyQt6.QtCore import QSettings
from .logger import APP_DATA_DIR


class SettingsManager:
    ORG_NAME = "MediaDownloader"
    APP_NAME = "MediaDownloader"
    SETTINGS_DIR = APP_DATA_DIR / "settings"
    SETTINGS_FILE = SETTINGS_DIR / "settings.ini"

    KEY_DEFAULT_FOLDER = "general/default_folder"
    KEY_THEME = "general/theme"
    KEY_DEFAULT_MODE = "general/default_mode"
    KEY_DEFAULT_AUDIO_FORMAT = "general/default_audio_format"
    KEY_DEFAULT_AUDIO_BITRATE = "general/default_audio_bitrate"
    KEY_CLIPBOARD_AUTOPASTE = "downloads/clipboard_autopaste"
    KEY_SHOW_NOTIFICATIONS = "downloads/show_notifications"
    KEY_SPEED_LIMIT = "downloads/speed_limit"
    KEY_INCLUDE_AUTO_SUBS = "subtitles/include_auto_generated"

    DEFAULTS = {
        KEY_DEFAULT_FOLDER: str(Path.home() / "Downloads"),
        KEY_THEME: "system",
        KEY_DEFAULT_MODE: "Video",
        KEY_DEFAULT_AUDIO_FORMAT: "mp3",
        KEY_DEFAULT_AUDIO_BITRATE: "320",
        KEY_CLIPBOARD_AUTOPASTE: False,
        KEY_SHOW_NOTIFICATIONS: True,
        KEY_SPEED_LIMIT: 0,
        KEY_INCLUDE_AUTO_SUBS: False,
    }

    def __init__(self):
        self.SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        self._settings = QSettings(str(self.SETTINGS_FILE), QSettings.Format.IniFormat)

    def load(self):
        return {
            self.KEY_DEFAULT_FOLDER: self.get_default_folder(),
            self.KEY_THEME: self.get_theme(),
            self.KEY_DEFAULT_MODE: self.get_default_mode(),
            self.KEY_DEFAULT_AUDIO_FORMAT: self.get_default_audio_format(),
            self.KEY_DEFAULT_AUDIO_BITRATE: self.get_default_audio_bitrate(),
            self.KEY_CLIPBOARD_AUTOPASTE: self.get_clipboard_autopaste(),
            self.KEY_SHOW_NOTIFICATIONS: self.get_show_notifications(),
            self.KEY_SPEED_LIMIT: self.get_speed_limit(),
            self.KEY_INCLUDE_AUTO_SUBS: self.get_include_auto_subs(),
        }

    def save(self, settings_dict):
        for key, default_value in self.DEFAULTS.items():
            value = settings_dict.get(key, default_value)
            self._settings.setValue(key, value)
        self._settings.sync()

    def _get_value(self, key):
        return self._settings.value(key, self.DEFAULTS[key])

    def get_default_folder(self):
        value = self._get_value(self.KEY_DEFAULT_FOLDER)
        return str(value) if value else self.DEFAULTS[self.KEY_DEFAULT_FOLDER]

    def set_default_folder(self, path):
        self._settings.setValue(self.KEY_DEFAULT_FOLDER, str(path))

    def get_theme(self):
        value = str(self._get_value(self.KEY_THEME)).lower()
        allowed = {"system", "dark", "light"}
        return value if value in allowed else self.DEFAULTS[self.KEY_THEME]

    def set_theme(self, value):
        normalized = str(value).lower()
        if normalized not in {"system", "dark", "light"}:
            normalized = self.DEFAULTS[self.KEY_THEME]
        self._settings.setValue(self.KEY_THEME, normalized)

    def get_default_mode(self):
        value = str(self._get_value(self.KEY_DEFAULT_MODE))
        return value if value in {"Video", "Audio"} else self.DEFAULTS[self.KEY_DEFAULT_MODE]

    def set_default_mode(self, mode):
        self._settings.setValue(self.KEY_DEFAULT_MODE, mode)

    def get_default_audio_format(self):
        value = str(self._get_value(self.KEY_DEFAULT_AUDIO_FORMAT))
        allowed = {"mp3", "m4a", "wav", "flac", "opus"}
        return value if value in allowed else self.DEFAULTS[self.KEY_DEFAULT_AUDIO_FORMAT]

    def set_default_audio_format(self, fmt):
        self._settings.setValue(self.KEY_DEFAULT_AUDIO_FORMAT, fmt)

    def get_default_audio_bitrate(self):
        value = str(self._get_value(self.KEY_DEFAULT_AUDIO_BITRATE))
        allowed = {"320", "256", "192", "128", "64"}
        return value if value in allowed else self.DEFAULTS[self.KEY_DEFAULT_AUDIO_BITRATE]

    def set_default_audio_bitrate(self, bitrate):
        self._settings.setValue(self.KEY_DEFAULT_AUDIO_BITRATE, bitrate)

    def get_clipboard_autopaste(self):
        return self._settings.value(self.KEY_CLIPBOARD_AUTOPASTE, self.DEFAULTS[self.KEY_CLIPBOARD_AUTOPASTE], type=bool)

    def set_clipboard_autopaste(self, enabled):
        self._settings.setValue(self.KEY_CLIPBOARD_AUTOPASTE, bool(enabled))

    def get_show_notifications(self):
        return self._settings.value(self.KEY_SHOW_NOTIFICATIONS, self.DEFAULTS[self.KEY_SHOW_NOTIFICATIONS], type=bool)

    def set_show_notifications(self, enabled):
        self._settings.setValue(self.KEY_SHOW_NOTIFICATIONS, bool(enabled))

    def get_speed_limit(self):
        return self._settings.value(self.KEY_SPEED_LIMIT, self.DEFAULTS[self.KEY_SPEED_LIMIT], type=int)

    def set_speed_limit(self, speed_limit):
        self._settings.setValue(self.KEY_SPEED_LIMIT, int(speed_limit))

    def get_include_auto_subs(self):
        return self._settings.value(self.KEY_INCLUDE_AUTO_SUBS, self.DEFAULTS[self.KEY_INCLUDE_AUTO_SUBS], type=bool)

    def set_include_auto_subs(self, enabled):
        self._settings.setValue(self.KEY_INCLUDE_AUTO_SUBS, bool(enabled))
