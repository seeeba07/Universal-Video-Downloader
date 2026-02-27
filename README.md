# Media Downloader

![Media Downloader App Screenshot](assets/screenshot.png)

## About

**Media Downloader** is a user-friendly desktop application built with PyQt6 that allows you to download videos and extract audio from various online platforms. Powered by `yt-dlp`, it supports YouTube, TikTok, Instagram, and many other video hosting services.

## Features

- Download videos in available formats and resolutions
- Extract audio (MP3, M4A, FLAC, OPUS, WAV)
- Ability to choose preferred framerate (if available)
- System info display (FFmpeg status, yt-dlp version, disk space)
- Customizable save location
- Subtitle downloading (if available)

## How to Use

### Getting Started

1. **Download** the latest release from the [Releases](../../releases) page
2. **Extract** the `.exe` file to your preferred location
3. **Run** the application - no installation needed

### Downloading Videos

1. Paste a video link from any supported platform
2. Click "Fetch" to retrieve available formats
3. Choose between **Video** or **Audio** mode
4. Select desired **Format** and **Quality**
5. Click "DOWNLOAD"

### Settings Explained

- Click the "?" for detailed explanations of each setting.

## Signature Warning

This application is **not code-signed**. When you download and run the `.exe` file, Windows may display security warnings such as:

```
Windows Defender SmartScreen prevents an unrecognized app from starting. Running this app might put your PC at risk.
```

**This is normal.** Code signing certificates are expensive and I'm not paying for that. To continue:

1. Click **"More info"** 
2. Click **"Run anyway"**
3. The application will launch normally

## Compiling from Source
If you want to compile the application yourself, download the `mdl.spec` file and make sure you have Python and PyInstaller installed, then run:

```bash
pyinstaller --clean --noconfirm mdl.spec
```

## One-Click Build (Portable + Installer)

Use `builds.bat` for a full build in one click.

What it does automatically:
- creates portable ZIP: `dist/media_downloader_portable_<version>.zip`
- builds installer EXE: `dist/media_downloader_setup_<version>.exe`

Version behavior:
- `builds.bat` uses the current version from `VERSION.txt` (no bump)
- `builds.bat bump` increments version first, then builds (release mode)

### Requirements

- Python environment with dependencies from `requirements.txt`
- PyInstaller installed
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) installed (for installer build) 

### Usage

1. For normal/team build: run `builds.bat`
2. For release build (version bump): run `builds.bat bump`
3. Wait for build to finish and find outputs in `dist/`

If Inno Setup is not installed, the script still builds the portable version and shows a warning.

## System Requirements

- **FFmpeg** (optional but recommended for best results)
  - Bundled in the portable package, or
  - Download from:
    [ffmpeg.org](https://ffmpeg.org/download.html)
    or via cmd using winget:
    ```
    winget install ffmpeg
    ```


## License: [MIT License](LICENSE)

You are free to:
- Use for personal and commercial purposes
- Modify and distribute
- Include in other projects

## Credits

Built with:
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - GUI Framework
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Video Downloader
- [FFmpeg](https://ffmpeg.org/) - Media Processor

## Issues & Feedback

Found a bug or have a suggestion? Please [open an issue](../../issues) on GitHub!

**Happy downloading!**
