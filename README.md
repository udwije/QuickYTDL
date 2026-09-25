# QuickYTDL 🎬

A fast, modern, open-source playlist and video downloader with a sleek PyQt6 GUI.  
Download single videos or entire playlists in your choice of Video resolutions or MP3, track per-item progress, and optionally shut down your machine when done.

---

## 🚀 Features (v1.4.0)

### 🎥 Playlist & Video Downloading
- Download entire YouTube playlists or single videos
- Choose from **Best available**, **4320p (8K)**, **2160p (4K)**, **1440p (2K)**, **1080p**, **720p**, **480p**, **360p**, or **MP3**
- Global format selector + per-video format override
- Automatic container selection: **.mkv** above 1080p, **.mp4** at 1080p and below

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

### 📦 Distribution
- 🖥️ Single-file **Windows executable** built from a committed PyInstaller spec
- 🧰 **MSI installer** with Start Menu / Desktop shortcuts and clean upgrades

---

## 📢 New in v1.4.0

### 🆕 High-Resolution Downloads
- Added **1440p**, **2160p (4K)** and **4320p (8K)** tiers
- New **Best available** option — now the default — always takes the highest quality a video offers
- Tiers above 1080p are saved as **.mkv**; YouTube publishes no MP4 above 1080p, since those streams are VP9 or AV1 and an MP4 container cannot hold them
- 1080p and below continue to produce **.mp4** exactly as before

### 🎯 Smarter Format Selection
- Quality selection now uses yt-dlp's `format_sort` instead of a hard height filter
- Requesting a resolution a video doesn't offer falls back to the next best available, rather than failing with *Requested format is not available*
- Format detection no longer scans for MP4 streams only — an MP4-only scan silently capped every video at 1080p
- Non-standard encode heights are snapped onto the nearest standard tier
- All quality/container logic consolidated into a single `quickytdl/formats.py` module

### 🐛 Fixes
- **Per-video format override** is now respected; the global selector previously overwrote every row's choice when the download started
- **Window and taskbar icon** now resolve correctly in the packaged executable via a `resource_path()` helper that handles PyInstaller's `sys._MEIPASS`
- **Crash guard** installed for unhandled exceptions, which PyQt6 otherwise turns into an instant `abort()` of the whole app
- Download worker refactored so no exception can escape `QThread.run()`
- Fixed a possible divide-by-zero in the progress bar delegate

### 📦 Packaging & Build
- Added `QuickYTDL.spec` — build the executable with a single `pyinstaller QuickYTDL.spec`
- Bundles ffmpeg and the app resources; registers yt-dlp's extractors as hidden imports so the frozen build doesn't fail with *Unsupported URL*
- Added `Build-Installer.ps1` and `installer/` to produce an MSI via WiX
- MSI installs per-machine, creates Start Menu and Desktop shortcuts, registers in Apps & Features, and upgrades cleanly over previous versions
- Supports silent install: `msiexec /i "QuickYTDL-1.4.0-x64.msi" /qn`

### ⬆️ Dependencies
- PyQt6 **6.5.2 → 6.9.1**
- yt-dlp **2025.4.30 → 2026.8.19**

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
