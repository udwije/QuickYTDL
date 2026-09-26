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

## JavaScript runtime (recommended)

Since yt-dlp 2025.11.12, YouTube extraction without an external JavaScript
runtime is deprecated: format availability is limited and degrades over
time, so higher resolutions may silently go missing.

Install Deno (recommended — it is the only runtime yt-dlp enables by
default):

```powershell
winget install --id=DenoLand.Deno
```

QuickYTDL also auto-detects Node or QuickJS on PATH and enables it for
yt-dlp explicitly, so any one of the three is enough. If none is found,
the app logs a one-line notice at startup and continues with reduced
format availability.

## Sanity checks before a release

```bash
python -m compileall -q .
python tools/check_init_order.py
```

`check_init_order.py` flags any `self.X` that `MainWindow.__init__` or
`_build_ui` reads before assigning. Qt widget construction is order
sensitive and this class of mistake only surfaces at runtime, as an
`AttributeError` on launch.

## Releasing

Releases are built by GitHub Actions on Windows runners, so you don't need a
local toolchain to publish one.

### Cut a release

```bash
git tag v1.7.1
git push origin v1.7.1
```

That triggers `.github/workflows/release.yml`, which:

1. derives the version from the tag (`v1.7.1` -> `1.7.1`);
2. stamps it into `version_info.txt` with `tools/set_version.py`, so the
   executable's file version always matches the tag;
3. runs the sanity checks (`compileall`, `check_init_order`, `check_theme`);
4. builds `QuickYTDL.exe` from `QuickYTDL.spec`;
5. builds the MSI, **if** `installer/` is present in the repo;
6. writes `SHA256SUMS.txt`;
7. publishes a GitHub Release with the artifacts attached and auto-generated
   notes.

### Rehearse without tagging

Actions -> **Release** -> *Run workflow*, enter a version, and leave
*draft* ticked. You get the same artifacts and a draft release you can
delete afterwards.

### Continuous checks

`.github/workflows/ci.yml` runs on every push to `main` and on pull
requests. It repeats the sanity checks and builds the executable, uploading
it as a short-lived artifact so you can test a change before tagging it.

### Note on the MSI

The MSI step is skipped automatically when `installer/QuickYTDL.wxs` and
`installer/License.rtf` are missing, and the release then ships the `.exe`
only. Commit the `installer/` directory to enable it.
