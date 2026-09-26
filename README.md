# QuickYTDL 🎬

A fast, modern, open-source playlist and video downloader with a sleek PyQt6 GUI.
Download single videos, entire playlists, or a pasted list of URLs in your choice of
video resolution or MP3, track per-item progress, and optionally shut down your
machine when everything is done.

---

## 🚀 Features

### 🎥 Downloading

- Download entire YouTube playlists or single videos
- 📋 **Batch mode** — paste a list of unrelated URLs and fetch them all at once
- ⚡ Batch URLs are fetched **concurrently**, and one bad link never aborts the rest
- 🎯 Quality tiers: **Best available**, **4320p (8K)**, **2160p (4K)**, **1440p (2K)**,
  **1080p**, **720p**, **480p**, **360p**, or **MP3**
- 🎚️ Sample rate selector (44.1 kHz / 48 kHz) for MP3 downloads
- 📦 Smart container choice — tiers above 1080p are saved as **.mkv**
  (YouTube publishes no MP4 above 1080p); 1080p and below stay **.mp4**
- 🪂 Graceful fallback — if an item doesn't offer the chosen resolution, the next
  best available is used instead of failing the download
- 🎛️ Global format selector plus a per-video format override
- ⏬ **Parallel downloads** with independent per-row progress

### 🛡️ Playlist Safety

- Playlist URLs inside a batch are flagged, grouped, and left **unticked** by default,
  so a stray `?list=` can never download hundreds of videos by accident
- ❓ **Confirmation prompt** before expanding playlist URLs, with a
  *first video only* option
- 🖱️ Right-click any row to select/deselect an entire source, keep only one source,
  or keep just a single video
- 🔀 Auto-generated playlists (Mix/radio, Liked, Watch Later) resolve straight to the
  single video rather than failing

### 💡 Interface

- 🌓 **Light and dark themes** with a one-click toggle, remembered between sessions
- 🎚️ **Segmented mode switch** — Single URL / URL List
- 🧮 **Selection toolbar** with a live *N of M selected* badge and
  All / None / Invert actions that respect the current filter
- 🔍 **Real-time search** filtering by video title or playlist name
- ✅ Select/deselect everything from the header checkbox
- 📈 **Overall progress bar** across the whole queue, alongside per-row bars
- 📊 Colour-coded progress reflecting each row's status at a glance
- 📶 Live speed and ETA per download, shown as one continuous 0–100% bar across
  the video and audio streams
- 🪧 Friendly empty-state placeholders instead of blank tables
- ❌ Cancel individual downloads mid-process, or everything at once
- 💬 Tooltips throughout; press **Enter** in the URL field to fetch
- 📄 **Log viewer** for fetch and download status

### 📁 Workflow

- 🗂️ Automatic subfolder creation from the playlist title
- 📅 Date-stamped folder for batch downloads
- 📂 Save path can be browsed or customised per download
- 💾 Settings persist via config — default path, theme, auto-shutdown
- 🧠 Smart default folder fallback: `~/Videos/QuickYTDL Downloads`
- ⚙️ **Auto-shutdown** option once downloads complete

### 🧩 Under the Hood

- 🛠️ **FFmpeg bundled** via imageio-ffmpeg — no separate installation needed
- 🔎 Auto-detects an installed JavaScript runtime (Deno / Node / QuickJS) and
  enables it for yt-dlp, so YouTube offers every available format
- 🧵 Safe thread lifecycle handling for fetch and download workers
- 🧪 Robust configuration system that tolerates missing or malformed paths

---

## 📦 Download

Grab the latest release from [Releases](https://github.com/udwije/QuickYTDL/releases):

| File | Use it for |
|---|---|
| `QuickYTDL-<version>-x64.msi` | Normal install — Start Menu and Desktop shortcuts, clean upgrades |
| `QuickYTDL-<version>-x64.exe` | Portable — run it straight from the file, no install |

Verify your download against the published `SHA256SUMS.txt`.

### Recommended

Install a JavaScript runtime so YouTube offers every format:

```powershell
winget install --id=DenoLand.Deno
```

Without one, higher resolutions may be unavailable.

---

## 🛠️ Build from Source

### Requirements

- Python 3.9+
- yt-dlp
- PyQt6
- imageio-ffmpeg

```bash
pip install -r requirements.txt
python main.py
```

### Bundle into a single executable

```bash
pip install pyinstaller
pyinstaller QuickYTDL.spec
```

This produces `dist/QuickYTDL.exe` — a single-file, windowed executable with the
app icon, version metadata, and the bundled ffmpeg binary all included, so it runs
standalone with no separate install step.

See [BUILD.md](BUILD.md) for the MSI installer and the release process.

---

## ⚠️ Disclaimer

- Use at your own risk. This software is provided "as-is", without warranties or guarantees.
- Respect YouTube's Terms of Service. Only download content you own or have permission to use.
- Bypassing certain protections may be restricted in your jurisdiction — please verify before use.

---

## 📄 License

This project is released under the **GPL-3.0** license.

### Dependencies & Their Licenses

- yt-dlp — Unlicense
- imageio-ffmpeg — BSD 3-Clause

Please carry forward their respective license notices if you redistribute.

---

## 🙏 Acknowledgements

💡 Built with Python, yt-dlp, and PyQt6. Powered by community contributions and
AI-assisted development.
