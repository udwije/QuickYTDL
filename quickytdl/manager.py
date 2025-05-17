# quickytdl/manager.py

import os
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from yt_dlp import YoutubeDL

from quickytdl.utils import sanitize_filename  # helper to strip illegal filename characters


class DownloadWorker(QThread):
    """
    QThread that downloads a single VideoItem via yt-dlp,
    emitting progress and finished signals back to the manager.
    """
    # Progress signal: (row_index, percent_complete, status_text)
    progress = pyqtSignal(int, float, str)
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
        # 1) Pre-check for cancellation
        if self.isInterruptionRequested():
            self.log.emit(f"⚠️ Cancelled before start: {self.item.title}")
            self.finished.emit(self.index, "Canceled")
            return

        # 2) Ensure the save directory exists
        try:
            os.makedirs(self.save_dir, exist_ok=True)
        except Exception as e:
            self.log.emit(f"❌ Cannot create save directory: {e}")
            self.finished.emit(self.index, "Failed")
            return

        # 3) Determine format string for yt-dlp
        height = None
        if isinstance(self.selected_format, str) and self.selected_format.endswith("p"):
            try:
                height = int(self.selected_format.rstrip("p"))
            except ValueError:
                height = None
        fmt = f"bestvideo[height<={height}]+bestaudio/best" if height else "best"

        # 4) Build a safe, sanitized output template
        safe_title = sanitize_filename(self.item.title)
        outtmpl = os.path.join(
            self.save_dir,
            f"{self.item.index:03d} - {safe_title}.%(ext)s"
        )
        # Also guard the parent directory of the outtmpl
        try:
            os.makedirs(os.path.dirname(outtmpl), exist_ok=True)
        except Exception:
            pass

        # 5) Setup yt-dlp options, including progress hook
        ydl_opts = {
            "format": fmt,
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._progress_hook],
        }

        # 6) Start download
        self.log.emit(f"⏬ Download #{self.item.index}: {self.item.title} [{self.selected_format}]")
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
        except Exception as e:
            # Common cause: missing ffmpeg for merging, or I/O error
            self.log.emit(f"❌ Error downloading #{self.item.index}: {e}")
            self.finished.emit(self.index, "Failed")
            return

        # 7) Post-download cancellation check
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
        """
        # If user requested cancelation, abort immediately
        if self.isInterruptionRequested():
            raise Exception("Download cancelled by user")

        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            downloaded = d.get("downloaded_bytes", 0)
            percent = (downloaded / total) * 100 if total else 0.0
            self.progress.emit(self.index, percent, "Downloading")
        elif status == "finished":
            # file downloaded, but merging may still be in progress
            self.progress.emit(self.index, 100.0, "Merging")


class DownloadManager(QObject):
    """
    Manages multiple DownloadWorker threads.
    Exposes unified progress, finished, and log signals for the UI.
    """
    progress = pyqtSignal(int, float, str)
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
        for item in items:
            worker = DownloadWorker(item, save_dir)
            worker.progress.connect(self.progress)
            worker.finished.connect(self.finished)
            worker.log.connect(self.log)
            self._workers.append(worker)

        # start them all
        for w in self._workers:
            w.start()

    def cancel_all(self):
        """
        Request interruption on all active DownloadWorker threads.
        """
        self.log.emit("🛑 Cancelling all downloads...")
        for w in self._workers:
            w.requestInterruption()
        # Optionally clear the list if these workers won't be reused
        self._workers.clear()
