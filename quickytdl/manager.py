# quickytdl/manager.py

import os
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QSemaphore
from yt_dlp import YoutubeDL
import imageio_ffmpeg as _iioffmpeg
# helper to strip illegal filename characters & format sizes
from quickytdl.utils import sanitize_filename, enabled_js_runtimes
from quickytdl import formats

_download_semaphore = QSemaphore(4)  #  max 4 concurrent downloads

class DownloadWorker(QThread):
    """
    QThread that downloads a single VideoItem via yt-dlp,
    emitting progress and finished signals back to the manager.
    """

    # index, percent, status, speed string, eta string
    progress = pyqtSignal(int, float, str, str, str)
    # Finished signal: (row_index, final_status_text)
    finished = pyqtSignal(int, str)
    # Log messages for UI
    log = pyqtSignal(str)

    def __init__(self, item, save_dir):
        super().__init__()
        self.item = item
        self.save_dir = save_dir
        # convert 1-based VideoItem.index to 0-based for signals/models
        self.index = item.index - 1
        self.url = getattr(item, "url", None)
        self.selected_format = getattr(item, "selected_format", None)

        # --- multi-stream progress tracking -------------------------------
        # A video tier downloads TWO streams (bv*+ba): video, then audio.
        # yt-dlp calls the progress hook separately for each, restarting at
        # 0%. Reporting that raw would make the bar fill, reset and fill
        # again, which reads as an endless download loop. We map each
        # stream onto its own slice of one overall bar instead.
        self._streams = []          # filenames seen, in order
        self._expected_streams = 1  # refined once we know the format
        self._last_percent = 0.0    # keeps the bar monotonic

    def run(self):
        _download_semaphore.acquire()
        try:
            self._run_download()
        except Exception as e:
            # Absolute safety net: PyQt6 will abort() the whole process if an
            # exception escapes a QThread.run() override, so nothing above
            # this point may ever be allowed to raise unhandled.
            from quickytdl.utils import timestamped
            self.log.emit(timestamped(f"❌ Unexpected error #{self.item.index}: {e}"))
            try:
                self.finished.emit(self.index, "Failed")
            except Exception:
                pass
        finally:
            _download_semaphore.release()

    def _run_download(self):
        # 1) Pre‐check for cancellation
        if self.isInterruptionRequested():
            self.log.emit(f"⚠️ Cancelled before start: {self.item.title}")
            self.finished.emit(self.index, "Canceled")
            return

        # 2) Ensure save dir exists
        try:
            os.makedirs(self.save_dir, exist_ok=True)
        except Exception as e:
            self.log.emit(f"❌ Cannot create save directory: {e}")
            self.finished.emit(self.index, "Failed")
            return

        # 3) Build format options based on user choice.
        # Delegated to quickytdl.formats so the tier list, the container
        # rule (MKV above 1080p) and the graceful-degrade sort all live in
        # one place.
        selected = self.selected_format
        format_opts = formats.build_format_opts(selected)

        # A muxed video tier pulls a separate video and audio stream; MP3
        # and any single-file fallback pull one. Used to slice the bar.
        self._expected_streams = (
            1 if selected == formats.MP3
            else (2 if '+' in str(format_opts.get('format', '')) else 1)
        )

        # 4) Safe output template
        safe_title = sanitize_filename(self.item.title)
        outtmpl = os.path.join(
            self.save_dir,
            f"{self.item.index:03d} - {safe_title}.%(ext)s"
        )
        os.makedirs(os.path.dirname(outtmpl), exist_ok=True)

        # 5) YDL opts (embed the bundled FFmpeg and enable progress hooks)
        from imageio_ffmpeg import get_ffmpeg_exe
        ydl_opts = {
            "outtmpl": outtmpl,
            "quiet": True,
            # yt-dlp prints the "No supported JavaScript runtime" notice
            # once per extraction; with parallel workers that floods the
            # console. We surface it once ourselves instead (see
            # js_runtime_note()).
            "no_warnings": True,
            "noprogress": True,
            "ffmpeg_location": get_ffmpeg_exe(),
            "progress_hooks": [self._progress_hook],
        }
        # Enable whichever JS runtime is installed. yt-dlp only turns on
        # deno by default, so a Node/QuickJS user would otherwise still get
        # degraded formats.
        _js = enabled_js_runtimes()
        if _js:
            ydl_opts["js_runtimes"] = _js
        # format / format_sort / merge_output_format
        ydl_opts.update(format_opts)

        # 6) MP3 postprocessing (only if MP3 selected)
        if selected == formats.MP3:
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
            sr = getattr(self.item, 'sample_rate', None)
            if sr:
                ydl_opts["postprocessor_args"] = ["-ar", str(sr)]

        # 7) Start download
        container = formats.container_for(selected)
        self.log.emit(
            f"⏬ Download #{self.item.index}: {self.item.title} "
            f"[{selected}{'' if selected == formats.MP3 else f' → {container}'}]"
        )
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
        except Exception as e:
            # check for cancellation keyword
            if "cancel" in str(e).lower():
                self.log.emit(f"⚠️ Download canceled #{self.item.index}")
                self.finished.emit(self.index, "Canceled")
                return
            else:
                from quickytdl.utils import timestamped
                self.log.emit(timestamped(f"❌ Download failed #{self.item.index}: {e}"))
                self.finished.emit(self.index, "Failed")
                return

        # 8) Final cancellation check
        if self.isInterruptionRequested():
            self.log.emit(f"⚠️ Download canceled #{self.item.index}")
            self.finished.emit(self.index, "Canceled")
        else:
            self.log.emit(f"✅ Completed #{self.item.index}")
            self.finished.emit(self.index, "Completed")

    def _progress_hook(self, d):
        """
        yt-dlp progress hook callback.
        Receives a dict with download status, emits percent+status.
        Checks for user cancellation and raises to exit cleanly.
        """
        # 🛑 Cancel if requested
        if self.isInterruptionRequested():
            self.log.emit(f"🛑 Cancel requested for #{self.item.index}")
            raise Exception("User cancelled download")

        status = d.get("status")

        if status in ("downloading", "finished"):
            slot = self._stream_slot(d)

        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)

            # Fraction of the CURRENT stream, then folded into the overall
            # bar so two streams read as one continuous 0-100%.
            frac = (downloaded / total) if total else 0.0
            frac = max(0.0, min(1.0, frac))
            percent = (slot + frac) / self._expected_streams * 100.0

            # Never let the bar go backwards; a retried fragment or a
            # re-estimated total would otherwise look like a restart.
            percent = max(self._last_percent, min(100.0, percent))
            self._last_percent = percent

            # format speed and ETA
            raw_speed = d.get("speed") or 0
            raw_eta = d.get("eta") or 0
            from quickytdl.utils import human_readable_size
            import time
            speed_str = human_readable_size(int(raw_speed)) + "/s"
            eta_str = time.strftime("%M:%S", time.gmtime(raw_eta))

            # While the audio stream is downloading, say so explicitly -
            # otherwise a second pass over the bar is confusing.
            label = "Downloading"
            if self._expected_streams > 1 and slot > 0:
                label = "Downloading audio"

            self.progress.emit(self.index, percent, label, speed_str, eta_str)

        elif status == "finished":
            # One stream finished. Only claim "Merging" once every expected
            # stream is done; otherwise the next stream is still to come.
            done_streams = slot + 1
            if done_streams >= self._expected_streams:
                self._last_percent = 100.0
                self.progress.emit(self.index, 100.0, "Merging", "", "")
            else:
                boundary = done_streams / self._expected_streams * 100.0
                self._last_percent = max(self._last_percent, boundary)
                self.progress.emit(
                    self.index, self._last_percent, "Downloading audio", "", ""
                )

    def _stream_slot(self, d) -> int:
        """
        Which stream (0-based) this hook callback belongs to.

        yt-dlp reports each stream under its own temporary filename, so a
        new filename means a new stream. Self-corrects _expected_streams if
        a format yields more parts than anticipated.
        """
        name = d.get("filename") or (d.get("info_dict") or {}).get("_filename")
        if not name:
            return max(0, len(self._streams) - 1)
        if name not in self._streams:
            self._streams.append(name)
        slot = self._streams.index(name)
        if slot + 1 > self._expected_streams:
            self._expected_streams = slot + 1
        return slot

class DownloadManager(QObject):
    """
    Manages multiple DownloadWorker threads.
    Exposes unified progress, finished, and log signals for the UI.
    """
    progress = pyqtSignal(int, float, str, str, str)
    finished = pyqtSignal(int, str)
    log = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._workers: list[DownloadWorker] = []

    def start_downloads(self, items, save_dir: str):
        """
        Spawn a DownloadWorker per VideoItem and kick them off.
        """
        # ensure top‐level folder exists
        os.makedirs(save_dir, exist_ok=True)

        count = len(items)
        self.log.emit(f"🚀 Starting {count} download{'s' if count != 1 else ''} to: {save_dir}")
        # clear any previous workers
        self._workers.clear()

        # create, wire, and store each worker
        for row, item in enumerate(items):
            worker = DownloadWorker(item, save_dir)
            # override the worker.index so progress maps to the download‐table row
            worker.index = row
            worker.progress.connect(self.progress)
            worker.finished.connect(self.finished)
            worker.log.connect(self.log)
            self._workers.append(worker)

        # start them all
        for w in self._workers:
            w.start()

    def cancel_all(self):
        self.log.emit("🛑 Cancelling all downloads…")
        # ask each worker to stop; they will emit `finished` themselves
        for w in self._workers:
            w.requestInterruption()
        # do NOT clear _workers here—let each one tear down in its own thread

