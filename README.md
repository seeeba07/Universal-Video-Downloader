# Media Downloader

![Media Downloader App Screenshot](assets/screenshot.png)

## About

**Media Downloader** is a user-friendly desktop application built with PyQt6 that allows you to download videos and extract audio from various online platforms. Powered by `yt-dlp`, it supports YouTube, TikTok, Instagram, and many other video hosting services.

## Features

- Download videos in available formats and resolutions
- Extract audio (MP3, M4A, FLAC, OPUS, WAV)
- Filename suffix tagging for video/audio (and playlist outputs)
- Choose preferred framerate (if available)
- ETA in download progress display
- System info display (FFmpeg status, yt-dlp version, disk space, app version)
- Customizable save location
- Subtitle downloading (manual + optional auto-generated subtitles)
- Playlist downloading support
- Download queue with per-item status/progress
- Queue management tools (remove item, clear finished, clear all with warning)
- Built-in yt-dlp updater
- Optional system tray integration (minimize to tray, tray menu, tray notifications)
- Settings dialog for defaults, theme, download behavior, and maintenance actions

## How to Use

### Getting Started

1. **Download** the latest release from the [Releases](../../releases) page
2. **Run** the setup file (`media_downloader_setup_<version>.exe`)
3. Complete the installer and launch **Media Downloader**

### Downloading Videos

1. Paste a video link from any supported platform
2. Click **Fetch** to load video information and available formats
3. Choose between **Video** or **Audio** mode
4. Select desired **Format** and **Quality**
5. Click **DOWNLOAD**

### Using the Queue

1. Configure mode/format/quality for the current URL
2. Click **ADD TO QUEUE** to enqueue with current settings snapshot
3. Repeat for more links
4. Click **START QUEUE** to process items sequentially
5. Use **CANCEL** (or **Shift + Cancel**) to stop current/all pending queue items

### Settings Explained

- Click the **?** button to see what each function does.
- Click the **⚙** button in the top-right corner to open Settings.
- Available options include:
  - Theme: **System (auto)** / **Dark** / **Light**
  - Default folder, mode, audio format, and bitrate
  - Auto-paste URL from clipboard on focus
  - Completion notification toggle
  - Download speed limit (KB/s)
  - Include auto-generated subtitles
  - Minimize to tray on close
  - Tray notifications on download/queue events
  - Maintenance tools: update yt-dlp, open/clear logs

### Data & Logs

The app stores local runtime data in:

- `~/.media_downloader/logs/app.log`
- `~/.media_downloader/settings/settings.ini`

## Signature Warning

This application is **not code-signed**. When you run the setup or app executable, Windows may display security warnings such as:

```
Windows Defender SmartScreen prevents an unrecognized app from starting. Running this app might put your PC at risk.
```

**This is normal** for unsigned apps. To continue:

1. Click **"More info"** 
2. Click **"Run anyway"**
3. The installation or app will proceed as normal.

## Compiling from Source
From the project root, make sure dependencies are installed and run:

```bash
pyinstaller --clean --noconfirm mdl.spec
```

## One-Click Build (Portable + Installer)

Use `builds.bat` for a full build in one click using version from `VERSION.txt`.

What it does automatically:
- creates portable ZIP: `dist/media_downloader_portable_<version>.zip`
- builds installer EXE: `dist/media_downloader_setup_<version>.exe`

### Requirements

- Python environment with dependencies from `requirements.txt`
- PyInstaller installed
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) installed (for installer build) 

### Usage

1. Run `builds.bat` from the project root
2. Wait for build to finish and find outputs in `dist/`

If Inno Setup is not installed, the script still builds the portable ZIP and shows a warning.

## System Requirements

- **FFmpeg** (optional but recommended for best results)
  - Bundled with release builds, or
  - Download from:
    [ffmpeg.org](https://ffmpeg.org/download.html)
    or via cmd using winget:
    ```
    winget install ffmpeg
    ```


## License: [GNU GPL v3](LICENSE)

This project is licensed under the **GNU General Public License v3.0**.

You can:
- Use, study, and modify the software
- Redistribute copies and modified versions

Under GPL v3 terms, redistributed versions must also remain under GPL-compatible terms and include source availability obligations.

## Credits

Built with:
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI Framework
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video Downloader
- [FFmpeg](https://ffmpeg.org/) - Media Processor

## Issues & Feedback

Found a bug or have a suggestion? Please [open an issue](../../issues) on GitHub!

**Happy downloading!**
