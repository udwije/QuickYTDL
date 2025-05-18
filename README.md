# QuickYTDL 🎬

A fast, modern, open-source Playlist downloader with a sleek PyQt6 GUI.  
Supports single videos & full playlists, per-item format selection, global format presets, real-time progress (with speed & ETA), auto-shutdown, and more.

> 💡 Built with Python, `yt-dlp`, and PyQt6. Powered by AI-assisted development.


https://github.com/user-attachments/assets/2e66109c-18a6-47c3-a3a8-96ce3d35e865

---

## 🚀 New in v1.1.0

- ✅ **Per-playlist subfolder** — each download run creates its own folder (first 20 chars of playlist title)  
- 🌐 **Global & per-video format** — set a default format for the entire batch, or override each row  
- 🎛️ **Select / Deselect All** via a header checkbox  
- 📊 **Live progress bar** with centered % text, plus **speed** (e.g. `1.2 MiB/s`) & **ETA** in the status bar  
- ⚙️ **Auto-shutdown** option once all downloads finish  
- 🛠️ **FFmpeg bundled** (via `imageio-ffmpeg`) for format merging — no external ffmpeg install needed  
- 🖼️ **Custom app & taskbar icon** on Windows  
- 📂 **Automatic default folder**: `~/Videos/QuickYTDL Downloads` (created if missing)  

---

## 📦 Download

Grab the latest `.exe` from [Releases](https://github.com/udwije/QuickYTDL/releases) and run—no install required.

---

## 🛠️ Build from Source

### Requirements

- Python 3.9+  
- `pip install -r requirements.txt`

### Generate resources

```bash
# Compile the Qt resource file:
pyside6-rcc quickytdl/resources/resources.qrc -o quickytdl/resources_rc.py
```
```bash
python main.py
```
```bash
pyinstaller --onefile --windowed \
  --icon quickytdl/resources/QuickYTDL.ico \
  --add-data "path\to\imageio_ffmpeg;imageio_ffmpeg" \
  main.py
```

## ⚖️ Legal Notice
This tool is for personal & educational use only. The author is not responsible for misuse.

## 📄 License

GPL

