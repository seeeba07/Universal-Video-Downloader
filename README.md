# Universal Video Downloader (UVD)

A feature-rich PyQt6 desktop application for downloading videos and extracting audio from YouTube, TikTok, and other supported platforms using **yt-dlp**.

![Python](https://img.shields.io/badge/Python-3.8+-3776ab.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-latest-41cd52.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ Features

- 🎬 **Video Download** - Download in various resolutions (up to 4K) with format selection
- 🎵 **Audio Extraction** - Extract audio in multiple formats (MP3, M4A, FLAC, OPUS, WAV)
- ⚙️ **Advanced Settings**
  - Quality/bitrate selection
  - FPS (frame rate) preferences
  - Video codec selection (AVC1, VP9, etc.)
  - Subtitle downloading and embedding
  - Browser cookie support (Chrome, Edge, Firefox, Opera)
- 🔄 **Robust Network Handling**
  - Automatic retry on failures (10 retries)
  - Parallel fragment downloads for faster speeds
  - Timeout protection
- 📊 **Real-time Progress Tracking** - Live download speed and progress display
- 💾 **Smart File Management**
  - Customizable download folder
  - Automatic temp file cleanup
  - Disk space monitoring
- 🎨 **Modern UI** - Dark-themed PyQt6 interface
- ⚡ **Performance Optimized**
  - Caching for FFmpeg location
  - Fast metadata fetching with playlist filtering
  - Concurrent operations

## 📋 Requirements

- **Python 3.8+**
- **FFmpeg** (required for audio extraction and video merging)
- **yt-dlp** (included in requirements)

### System Requirements

- **OS**: Windows, macOS, or Linux
- **RAM**: Minimum 2GB (4GB+ recommended)
- **Disk Space**: Varies by download quality

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/universal-video-downloader.git
cd universal-video-downloader/downloader
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Install FFmpeg

**Windows:**
- Download from [ffmpeg.org](https://ffmpeg.org/download.html) or use Chocolatey:
  ```bash
  choco install ffmpeg
  ```
- Or place `ffmpeg.exe` in the application folder

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install ffmpeg
```

### 4. Run the Application
```bash
python uvd.py
```

## 📖 Usage

### Basic Workflow

1. **Paste URL** - Enter a video link in the input field (auto-detects and fetches metadata)
2. **Select Type** - Choose between "Video" or "Audio"
3. **Configure Settings**
   - For **Video**: Select format, FPS, resolution
   - For **Audio**: Select format, bitrate
   - Optional: Enable subtitles, configure cookies
4. **Choose Folder** - Select where to save downloads
5. **Click Download** - Start the process

### Video Download Settings

| Setting | Options | Purpose |
|---------|---------|---------|
| Format | mp4, webm, mkv, etc. | Container format & codec |
| FPS | 24, 30, 60, etc. | Frame rate preference |
| Quality | Resolution options | Video resolution & bitrate |
| Subtitles | On/Off | Download & embed subtitles |

### Audio Extraction Settings

| Setting | Options | Purpose |
|---------|---------|---------|
| Format | mp3, m4a, flac, opus, wav | Audio codec & format |
| Quality | 64-320 kbps | Audio bitrate |

### Cookie Support

Use cookies from your browser to:
- Access age-restricted content
- Download from premium accounts
- Bypass regional restrictions

Select your browser from the "Cookies" dropdown before downloading.

## ⚙️ Configuration

### Download Folder
By default, files are saved to `~/Downloads`. Use the "Change" button to select a custom location.

### FFmpeg Detection
The app automatically searches for FFmpeg in this order:
1. Bundled with PyInstaller executable
2. Local application folder
3. System PATH
4. Common Windows installation paths
5. Returns an error if not found

## 📁 Project Structure

```
downloader/
├── uvd.py              # Main application
├── requirements.txt    # Dependencies
├── uvd.spec           # PyInstaller configuration
├── README.md          # This file
├── icon.ico           # Application icon
└── build/             # Build output (PyInstaller)
```

## 🔧 Dependencies

See [requirements.txt](requirements.txt):
```
PyQt6>=6.0.0
yt-dlp>=2024.0.0
```

## 🛠️ Building an Executable

To create a standalone `.exe` for Windows:

```bash
pip install pyinstaller
pyinstaller uvd.spec
```

The executable will be in the `dist/` folder.

## ⚠️ Troubleshooting

### FFmpeg Not Found
- Ensure FFmpeg is installed and in your system PATH
- Check the status bar at the bottom of the app for FFmpeg status
- On Windows, place `ffmpeg.exe` in the application folder

### Download Fails
- Verify the URL is correct and supported
- Check your internet connection
- Try enabling cookies from your browser
- Some content may be geographically restricted

### Audio Format Not Available
- Not all formats support thumbnails and metadata
- Verified formats: MP3, M4A, FLAC, OPUS, WAV

### Permission Denied on Download Folder
- Change the download folder to a location where you have write permissions
- Check disk space availability

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚖️ Legal Notice

This tool is for **personal use only**. Respect copyright laws and terms of service of content creators and platforms. The developer is not responsible for misuse or copyright violations.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request or open an Issue for bugs and feature requests.

## 📧 Support

For issues, questions, or suggestions, please open an [Issue](https://github.com/yourusername/universal-video-downloader/issues) on GitHub.

---

**Created with ❤️ by Sebastian Macura**
