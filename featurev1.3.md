# 🎵 QuickYTDL | Multi-Playlist Downloader

A PyQt6-based desktop application for downloading multiple YouTube playlists simultaneously using `yt-dlp`, with support for MP3 conversion via `imageio-ffmpeg`. The app offers a clean UI, parallel downloads, and real-time progress feedback.

---

## ✨ Features

- ✅ Paste multiple playlist URLs and fetch details
- ✅ Download playlists in parallel
- ✅ Select individual or global video formats (e.g. 1080p, mp3)
- ✅ Convert videos to MP3 with quality options (e.g. 44kHz)
- ✅ Progress bars and cancel buttons for each video/playlist
- ✅ Persistent logging and error handling

---

## 🖼️ App Workflow

1. **Paste URLs** (one per line) in the Fetch pane and click **Fetch**.
2. **Fetched Playlists** appear in dynamic tables inside resizable cells.
3. **Select Formats & Options**:
   - Choose formats per-video or globally
   - Optionally enable MP3 conversion (with 44kHz/42kHz)
   - Set download location
4. Click **Download** to start.
5. **Download Pane** appears with:
   - Playlist-specific tables
   - Per-video progress bars and cancel buttons
   - Playlist-wide progress and control
6. Optionally click **Global Cancel** to terminate all downloads.

---

## 🧩 Tech Stack

| Tool              | Purpose                           |
|-------------------|-----------------------------------|
| `PyQt6`           | GUI Framework                     |
| `yt-dlp`          | Video/Playlist download engine     |
| `imageio-ffmpeg`  | MP3 conversion                    |
| `threading`       | Parallel downloads                |
| `subprocess`      | External process handling         |
| `json`, `os`      | Config and file management        |

---

## 🗂️ Project Structure
```bash
multi_playlist_downloader/
├── main.py # Entry point
├── ui/
│ ├── fetch_pane.py # UI for URL entry and playlist fetch
│ ├── download_pane.py # UI for progress and cancel controls
│ ├── global_controls.py # Global options & controls
│ └── widgets/
│ ├── playlist_table.py # Custom QTableWidgets per playlist
│ ├── row_widget.py # Checkbox + format dropdown rows
│ └── progress_bar_widget.py # Custom progress bar component
├── core/
│ ├── fetcher/
│ │ ├── url_parser.py # Validate & clean URLs
│ │ └── metadata_fetcher.py # yt-dlp metadata fetching
│ ├── downloader/
│ │ ├── download_manager.py # Handle concurrent playlist downloads
│ │ ├── worker_thread.py # Worker for individual video download
│ │ └── progress_updater.py # Emit download status updates
│ ├── converter/
│ │ └── mp3_converter.py # MP3 conversion logic
│ └── utils/
│ ├── file_utils.py # File naming & location helpers
│ ├── config.py # Load/save user settings
│ └── logger.py # Unified logging (UI + file)
├── resources/
│ ├── app_icon.png
│ └── style.qss # Optional styling
├── settings/
│ └── config.json # Format, path, quality defaults
├── logs/
│ └── app.log # Persistent log file
├── requirements.txt
└── README.md

```
---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/multi-playlist-downloader.git
cd multi-playlist-downloader
```
2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate
```
3. Install Dependencies
```bash
pip install -r requirements.txt
```
🧪 Run the App
```bash
python main.py
```
🛠️ Build Executable (Optional)
With PyInstaller:
```bash
pyinstaller --noconfirm --onefile --windowed --icon=resources/app_icon.png main.py
The executable will be in dist/.
```

📦 Requirements
```bash
yt-dlp
PyQt6
imageio-ffmpeg
```
🧠 TODO
 Drag & drop support for URLs

 Auto-retry on failed downloads

 Theme customization

 Export fetched metadata as CSV
---
📜 License
MIT License. See LICENSE for more.

🙋‍♀️ Maintainers
[Your Name] – @github

💡 Tips
Make sure ffmpeg is available in your system PATH

Check logs/app.log for errors or failed downloads

The download folder is user-selectable before download begins

---
