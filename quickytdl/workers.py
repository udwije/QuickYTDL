# quickytdl/workers.py

import os
from PyQt6.QtCore import QThread, pyqtSignal
from yt_dlp import YoutubeDL


class DownloadWorker(QThread):
    """
    QThread that downloads a single VideoItem via yt-dlp,
    emitting progress, finished, and log signals.
    """
    # index (0-based), percent complete, status
    progress = pyqtSignal(int, float, str)
    # index (0-based), final status
    finished = pyqtSignal(int, str)
    # log messages
    log = pyqtSignal(str)

    def __init__(self, item, save_dir):
        super().__init__()
        self.item = item
        self.save_dir = save_dir
        # convert 1-based VideoItem.index to 0-based for signaling/model
        self.index = item.index - 1
        self.url = getattr(item, "url", None)
        self.selected_format = getattr(item, "selected_format", None)

    def run(self):
        # check for pre‐start cancellation
        if self.isInterruptionRequested():
            self.log.emit(f"⚠️ Cancelled before start: {self.item.title}")
            self.finished.emit(self.index, "Canceled")
            return

        # parse height from format string like "720p"
        height = None
        if isinstance(self.selected_format, str) and self.selected_format.endswith("p"):
            try:
                height = int(self.selected_format.rstrip("p"))
            except ValueError:
                height = None

        # build format selector
        fmt = f"bestvideo[height<={height}]+bestaudio/best" if height else "best"
        # output template: zero‐padded index and title
        outtmpl = os.path.join(
            self.save_dir,
            f"{self.item.index:03d} - %(title)s.%(ext)s"
        )

        ydl_opts = {
            "format": fmt,
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._progress_hook],
        }

        self.log.emit(f"⏬ Starting download #{self.item.index}: {self.item.title} [{self.selected_format}]")
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
        except Exception as e:
            self.log.emit(f"❌ Error downloading #{self.item.index}: {e}")
            self.finished.emit(self.index, "Failed")
            return

        # check for cancellation mid‐download
        if self.isInterruptionRequested():
            self.log.emit(f"⚠️ Download canceled #{self.item.index}")
            self.finished.emit(self.index, "Canceled")
        else:
            self.log.emit(f"✅ Completed #{self.item.index}")
            self.finished.emit(self.index, "Completed")

    def _progress_hook(self, d):
        """
        yt-dlp progress hook: emits download percent and status.
        """
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            downloaded = d.get("downloaded_bytes", 0)
            percent = (downloaded / total * 100) if total else 0.0
            self.progress.emit(self.index, percent, "Downloading")
        elif status == "finished":
            # file has been downloaded, but merging/muxing may follow
            self.progress.emit(self.index, 100.0, "Merging")
