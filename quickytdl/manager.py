# quickytdl/manager.py

import os
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QSemaphore
from yt_dlp import YoutubeDL
import imageio_ffmpeg as _iioffmpeg
# helper to strip illegal filename characters & format sizes
from quickytdl.utils import sanitize_filename, human_readable_size  

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

    def run(self):
        _download_semaphore.acquire()
        try:
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

            # 3) Build exact format string based on user choice
            selected = self.selected_format
            if selected == "mp3":
                fmt = "bestaudio/best"
            elif selected in ["1080p", "720p", "480p", "360p"]:
                height = int(selected.rstrip("p"))
                # MP4 video at exact height + M4A audio, fallback to ≤height then any MP4
                fmt = (
                    f"bestvideo[height={height}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"best[ext=mp4]"
                )
            else:
                fmt = "best"

            # 4) Safe output template
            safe_title = sanitize_filename(self.item.title)
            outtmpl = os.path.join(
                self.save_dir,
                f"{self.item.index:03d} - {safe_title}.%(ext)s"
            )
            os.makedirs(os.path.dirname(outtmpl), exist_ok=True)

            # 5) YDL opts (include embedded ffmpeg)
            from imageio_ffmpeg import get_ffmpeg_exe
            ydl_opts = {
                "format": fmt,
                "outtmpl": outtmpl,
                "quiet": True,
                "no_warnings": True,
                "progress_hooks": [self._progress_hook],
                "ffmpeg_location": get_ffmpeg_exe(),
            }

            # 6) MP3 postprocessing (only if MP3 selected)
            if selected == "mp3":
                ydl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
                # apply sample rate from UI if provided
                sr = getattr(self.item, 'sample_rate', None)
                if sr:
                    ydl_opts["postprocessor_args"] = ["-ar", str(sr)]

            # 7) Start download
            self.log.emit(f"⏬ Download #{self.item.index}: {self.item.title} [{selected}]")
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])

            # 8) Final cancellation check
            if self.isInterruptionRequested():
                self.log.emit(f"⚠️ Download canceled #{self.item.index}")
                self.finished.emit(self.index, "Canceled")
            else:
                self.log.emit(f"✅ Completed #{self.item.index}")
                self.finished.emit(self.index, "Completed")
        finally:
            _download_semaphore.release()

    def _progress_hook(self, d):
        """
        yt-dlp progress hook callback.
        Receives a dict with download status, emits percent+status.
        """
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            downloaded = d.get("downloaded_bytes", 0)
            # compute percent
            percent = (downloaded / total) * 100 if total else 0.0
            # format speed and ETA
            raw_speed = d.get("speed") or 0
            raw_eta   = d.get("eta")   or 0
            from quickytdl.utils import human_readable_size
            import time
            speed_str = human_readable_size(int(raw_speed)) + "/s"
            eta_str   = time.strftime("%M:%S", time.gmtime(raw_eta))
            # emit full five‐argument signal
            self.progress.emit(
                self.index,
                percent,
                "Downloading",
                speed_str,
                eta_str,
            )
        elif status == "finished":
            # file downloaded, but merging may still be in progress
            self.progress.emit(self.index, 100.0, "Merging", "", "")


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


