# Building QuickYTDL

## Run from source

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Build the executable

```bash
pip install pyinstaller
pyinstaller QuickYTDL.spec
```

Output: `dist/QuickYTDL.exe` — single file, windowed, with the app icon,
version metadata and the bundled ffmpeg binary included.

Rebuild after any code change with the same command. If PyInstaller appears
to use stale cached files, delete `build/` and `dist/` first.

## Smoke test after building

Run `dist/QuickYTDL.exe` on a machine **without** Python installed, and check:

1. **Window and taskbar icon appear.** If the window is icon-less, the
   `resources/` bundle or `resource_path()` lookup isn't resolving under
   `sys._MEIPASS`.
2. **Fetch a playlist URL.** An `Unsupported URL` error here means the
   yt-dlp extractors were not bundled — confirm `hiddenimports=['yt_dlp.extractor']`
   survived in the spec.
3. **Download one item at 2160p or Best available.** Confirm the output is
   a playable `.mkv`. A 0-byte or corrupt file, or an ffmpeg exit code like
   `-1073741819`, points at the bundled ffmpeg being UPX-compressed — the
   spec's `upx_exclude` should prevent this.
4. **Download one item at 1080p.** Confirm it is still `.mp4`, i.e. the
   pre-existing behaviour is unchanged.
5. **Download one item as MP3** and confirm the sample-rate selector applies.

## Notes

- Tiers above 1080p are written as `.mkv` because YouTube publishes no
  MP4/H.264 above 1080p — those streams are VP9 or AV1, which an MP4
  container cannot hold. 1080p and below still produce `.mp4`.
- Quality selection uses yt-dlp's `format_sort`, not a hard height filter,
  so an item that doesn't offer the requested resolution falls back to the
  next best available instead of failing the download.
- `QuickYTDL-crash-fix.patch` in the repo root is fully applied to this
  tree already. It is kept only for history — do not re-apply it, as it
  will conflict with `quickytdl/manager.py`.
