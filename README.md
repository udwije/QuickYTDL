# QuickYTDL 🎬

A fast, modern, open-source playlist and video downloader with a sleek PyQt6 GUI.  
Download single videos or entire playlists in your choice of Video resolutions or MP3, track per-item progress, and optionally shut down your machine when done.

---

## 🚀 Features (v1.3.0)

### 🎥 Playlist & Video Downloading
- Download entire YouTube playlists or single videos
- Choose from **1080p**, **720p**, **480p**, **360p**, or **MP3**
- Global format selector + per-video format override

### 💡 Enhanced UI & Experience
- 🔍 **Real-time Playlist Search** with live filtering
- ✅ **Select/Deselect All** via header checkbox
- ⏬ **Parallel Downloads** with per-row progress
- 📶 Live speed and ETA shown per download
- ❌ **Cancel individual downloads** mid-process
- 📄 **Log viewer** for fetch and download status
- ⚙️ **Auto-shutdown** option after downloads

### 📁 Workflow Features
- 🗂️ Automatic subfolder creation using playlist title
- 📂 Save path can be browsed or customized
- 💾 User settings (default path, shutdown, etc.) persist via config
- 🧠 Smart default folder fallback: `~/Videos/QuickYTDL Downloads`

---

## 📢 New in v1.3.0

- 🆕 **Download Progress Redesign**  
  - Live ETA, speed, and percentage using visually styled blocks  
  - Per-row progress delegate with cancel button  

- 🧠 **Improved Search & Filter**  
  - Toggle between URL input and search bar  
  - Fuzzy title filtering based on keyword match  

- 📋 **Unified Signal Management**  
  - Better thread lifecycle handling  
  - Safer teardown for fetch/download threads  

- 🧪 **Robust Configuration System**  
  - Handles missing/malformed paths  
  - Persists default save location and auto-shutdown preference  

- 🖥️ **Clean UI Layouts**  
  - Grouped controls with clear hierarchy  
  - Icons for toggling log and advanced settings views  
  - Updated default save folder logic with path validation

---
<img width="1920" height="1030" alt="" src="https://github.com/user-attachments/assets/e133881a-8dc7-4bac-815f-3f8777a8dcfa" />
<img width="1920" height="1030" alt="" src="https://github.com/user-attachments/assets/36074e02-78fe-472f-9a05-c11fa12eece0" />
<img width="1920" height="1030" alt="" src="https://github.com/user-attachments/assets/fc1468b7-7a33-4613-aec4-063b2ab60021" />
<img width="1920" height="1032" alt="" src="https://github.com/user-attachments/assets/4bf04dc7-9b37-4ded-8a43-de92d88352cf" />
<img width="1920" height="1030" alt="" src="https://github.com/user-attachments/assets/d57d10e7-98d0-44bc-af85-4ab58a0d3994" />

---

## 🔄 Changelog

## 📢 v1.2.0 – Audio Only Downloads

### 🎵 MP3 Download Support
- Extract and download playlist items as **MP3** files.

### 🎚 Sample Rate Selector
- Choose between **44.1 kHz** or **48 kHz** when downloading MP3s.

### 🤖 Smarter Button States
- 🔗 **Fetch** enabled only when a valid URL is entered  
- 🟢 **Download** becomes active once at least one video is selected  
- ❌ **Cancel** remains active during all processes  

### 🗒 Cleaned-up Logging
- Removed duplicate entries in the complete log

### 🛠 UI Reliability Improvements
- Prevents zombie threads and dangling connections after fetch/download

## 🔥 v1.1.0 – Stability & Format Controls

### ✅ Download Controls
- Subfolder creation based on playlist title (up to 20 characters)
- Global and per-row format selection
- Header checkbox to **Select/Deselect All**

### 📶 Real-time Progress Feedback
- Percent, speed, and ETA shown for each active download

### ⚙️ Settings & Environment
- **Auto-shutdown** toggle after download completes
- **FFmpeg bundled** via `imageio-ffmpeg`—no separate installation needed
- **Custom app/taskbar icon** on Windows
- **Default save directory** auto-created in `~/Videos/QuickYTDL Downloads`

---

## 📦 Download

Grab the latest `.exe` from [Releases](https://github.com/udwije/QuickYTDL/releases) and run—no install required.

No installation requried. Download & Run.

---

## 🛠️ Build from Source

### Requirements

- `Python 3.9+`  
- `yt-dlp`  
- `PyQt6`  
- `imageio-ffmpeg`  

```bash
pip install -r requirements.txt
```
### Generate resources

```bash
# Launch the app
python main.py
```

(Optional) Bundle into a Single Executable
```bash
pyinstaller --onefile --windowed \
  --icon quickytdl/resources/QuickYTDL.ico \
  --add-data "path\to\imageio_ffmpeg;imageio_ffmpeg" \
  main.py
```
---
## ⚠️ Disclaimer

* Use at your own risk. This software is provided “as-is”, without warranties or guarantees.
* Respect YouTube’s Terms of Service. Only download content you own or have permission to use.
* Bypassing certain protections may be restricted in your jurisdiction—please verify before use.
  
---

## 📄 License

This project is released under the GPL-3.0 license.

# Dependencies & Their Licenses
  * yt-dlp — Unlicense
  * imageio-ffmpeg — BSD 3-Clause

Please carry forward their respective license notices if you redistribute.

---

## 🙏 Acknowledgements

> 💡Built with Python, yt-dlp, and PyQt6. Powered by community contributions and AI-assisted development.
