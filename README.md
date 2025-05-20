# QuickYTDL 🎬

A fast, modern, open-source playlist and video downloader with a sleek PyQt6 GUI.  
Download single videos or entire playlists in your choice of Video resolutions or MP3, track per-item progress, and optionally shut down your machine when done.

---


https://github.com/user-attachments/assets/dfb8a41d-1fdb-42f0-8f00-9339aa161b22


---

## 📢 New in v1.2.0 (Audio Branch)

- 🎵 **MP3 Download Support**  
  Download playlists or individual videos as MP3 files.

- 🎚️ **Sample-Rate Selector**  
  When “mp3” is chosen as the global format, choose between 44.1 kHz or 48 kHz.

- 🤖 **Smarter Button States**  
  - 🔗 **URL Validation**  
    The **Fetch** button is only enabled when the URL field contains a non-empty, valid URL.  
  - 🟢 **Download Enablement**  
    The **Download** button becomes enabled as soon as at least one item is selected.  
  - ❌ **Cancel Always Available**  
    The **Cancel** button remains clickable at all times—so you can abort fetching or downloading mid-stream.

- 🗒️ **Cleaned-up Logging**  
  Duplicate log entries in the **Complete Log** tab have been eliminated—every status message now appears only once.

- 🛠️ **Improved UI Reliability**  
  Under-the-hood refactors ensure no more “zombie” threads or dangling signal connections.
  
---

## 🔥 What’s Already in v1.1.0

- ✅ **Per-Playlist Subfolder**  
  Each download run creates its own folder named after the first 20 characters of the playlist title.  
- ✅ **Global & Per-Video Format Overrides**  
  Set a default format for the entire batch, or pick a different format for each row.  
- ✅ **Select/Deselect All** via a header checkbox.  
- ✅ **Live Progress Bars**  
  Centered % text in each row, plus overall speed & ETA in the status bar.  
- ⚙️ **Auto-Shutdown Option**  
  Have your machine shut down when all downloads finish.  
- 🎞️ **Bundled FFmpeg** (via `imageio-ffmpeg`)—no separate install required.  
- 🖼️ **Custom App & Taskbar Icon** on Windows.  
- 📂 **Automatic Default Folder**  
  `~/Videos/QuickYTDL Downloads` is created if missing.

---

## 📦 Download

Grab the latest `.exe` from [Releases](https://github.com/udwije/QuickYTDL/releases) and run—no install required.

---

## 🛠️ Build from Source

### Requirements

- Python 3.9+  
- `yt-dlp`  
- PyQt6  
- `imageio-ffmpeg`  

```bash
pip install -r requirements.txt
```
### Generate resources

```bash
# Compile the Qt resource file:
pyside6-rcc quickytdl/resources/resources.qrc -o quickytdl/resources_rc.py
```

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
