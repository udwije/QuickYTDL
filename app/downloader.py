# =========================
# app/downloader.py
# =========================

import threading
import queue
import yt_dlp
from app.models import PlaylistItem
from PyQt5.QtCore import QObject

class DownloadWorker(threading.Thread):
    def __init__(self, task_queue, signals):
        super().__init__()
        self.task_queue = task_queue
        self.signals = signals
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            try:
                item, format_code = self.task_queue.get(timeout=1)
            except queue.Empty:
                break

            self.download_item(item, format_code)
            self.task_queue.task_done()

    def download_item(self, item: PlaylistItem, format_code: str):
        # Update status to queued
        item.update_status("⏳")
        self.signals.status_update.emit(item.index, item.status)

        ydl_opts = {
            'format': format_code,
            'outtmpl': f'%(title)s.%(ext)s',
            'progress_hooks': [lambda d: self.progress_hook(d, item)],
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([item.url])
            item.update_status("✅")
        except Exception as e:
            item.update_status("❌")
            self.signals.log_output.emit(f"Download failed for {item.title}: {str(e)}")

        self.signals.status_update.emit(item.index, item.status)

    def progress_hook(self, d, item):
        if d['status'] == 'downloading':
            item.update_status("⏳")
            self.signals.status_update.emit(item.index, item.status)
        elif d['status'] == 'finished':
            item.update_status("✅")
            self.signals.status_update.emit(item.index, item.status)

    def stop(self):
        self._stop_event.set()

class DownloadManager(QObject):
    def __init__(self, signals):
        super().__init__()
        self.signals = signals
        self.task_queue = queue.Queue()
        self.worker = None

    def start_downloads(self, items, format_code="best"):
        if self.worker and self.worker.is_alive():
            self.signals.log_output.emit("Download already in progress.")
            return

        for item in items:
            if item.get('selected', False):  # Access 'selected' key
                self.task_queue.put((item, format_code))

        self.worker = DownloadWorker(self.task_queue, self.signals)
        self.worker.start()



    def cancel_downloads(self):
        if self.worker:
            self.worker.stop()
            self.signals.log_output.emit("Downloads cancelled.")
