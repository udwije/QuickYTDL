# quickytdl/manager.py

import os
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from yt_dlp import YoutubeDL


class DownloadWorker(QThread):
    """
    QThread that downloads a single VideoItem via yt-dlp,
    emitting progress and finished signals back to the manager.
    """
    # index (0-based), percent complete, status text
    progress = pyqtSignal(int, float, str)
    # index (0-based), final status text
    finished = pyqtSignal(int, str)
    # log messages
    log = pyqtSignal(str)

    def __init__(self, item, save_dir):
        super().__init__()
        self.item = item
        self.save_dir = save_dir
        # use 0-based index in signals/models
        self.index = item.index - 1
        self.url = getattr(item, "url", None)
        self.selected_format = getattr(item, "selected_format", None)

    def run(self):
        # check if cancelled before starting
        if self.isInterruptionRequested():
            self.log.emit(f"⚠️ Cancelled before start: {self.item.title}")
            self.finished.emit(self.index, "Canceled")
            return

        # parse desired height from "1080p", etc.
        height = None
        if self.selected_format and self.selected_format.endswith("p"):
            try:
                height = int(self.selected_format.rstrip("p"))
            except ValueError:
                height = None

        # build yt-dlp format string
        fmt = f"bestvideo[height<={height}]+bestaudio/best" if height else "best"
        # filename template: "001 - Title.ext"
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

        self.log.emit(f"⏬ Download #{self.item.index}: {self.item.title} [{self.selected_format}]")
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
        except Exception as e:
            self.log.emit(f"❌ Error downloading #{self.item.index}: {e}")
            self.finished.emit(self.index, "Failed")
            return

        # final check for cancellation
        if self.isInterruptionRequested():
            self.log.emit(f"⚠️ Download cancelled #{self.item.index}")
            self.finished.emit(self.index, "Canceled")
        else:
            self.log.emit(f"✅ Completed #{self.item.index}")
            self.finished.emit(self.index, "Completed")

    def _progress_hook(self, d):
        """
        yt-dlp progress hook.
        Emits percent downloaded and status.
        """
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            downloaded = d.get("downloaded_bytes", 0)
            percent = downloaded / total * 100 if total else 0.0
            self.progress.emit(self.index, percent, "Downloading")
        elif status == "finished":
            # downloaded but not merged yet
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
        Spawn a DownloadWorker for each VideoItem in `items`
        and start them.
        """
        os.makedirs(save_dir, exist_ok=True)
        count = len(items)
        self.log.emit(f"🚀 Starting {count} download{'s' if count!=1 else ''} to: {save_dir}")
        self._workers.clear()

        for item in items:
            worker = DownloadWorker(item, save_dir)
            # wire worker signals through to manager signals
            worker.progress.connect(self.progress)
            worker.finished.connect(self.finished)
            worker.log.connect(self.log)
            self._workers.append(worker)

        # start all workers
        for w in self._workers:
            w.start()

    def cancel_all(self):
        """
        Request interruption on all running workers.
        """
        self.log.emit("🛑 Cancelling all downloads...")
        for w in self._workers:
            w.requestInterruption()
        # Optionally clear the list if you won't restart them
        self._workers.clear()
