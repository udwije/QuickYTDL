import os
import re
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QCheckBox, QFileDialog, QProgressBar, QPlainTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from yt_dlp import YoutubeDL
from PyQt5.QtGui import QIcon

# Regex to remove ANSI escape sequences from yt-dlp logs
ANSI_ESCAPE = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')

def strip_ansi_escape(text):
    return ANSI_ESCAPE.sub('', text)


class DownloadWorker(QThread):
    log_output = pyqtSignal(str)
    finished = pyqtSignal()
    video_titles = pyqtSignal(list)
    progress_updated = pyqtSignal(int, str, str)  # percent, eta, speed

    def __init__(self, url, output_path, format_option, is_playlist):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self.format_option = format_option
        self.is_playlist = is_playlist

    def hook(self, d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%').strip()
            speed = d.get('_speed_str', '0 KiB/s').strip()
            eta = d.get('eta', 0)

            try:
                percent_value = int(float(percent.strip('%')))
            except:
                percent_value = 0

            eta_str = f"{eta}s" if eta else "?"
            self.progress_updated.emit(percent_value, eta_str, speed)

        elif d['status'] == 'finished':
            self.progress_updated.emit(100, "0s", "0 KiB/s")

    def fetch_video_list(self):
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_generic_extractor': True
        }
        video_titles = []

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(self.url, download=False)
                if 'entries' in info_dict:
                    for entry in info_dict['entries']:
                        title = entry.get('title', 'Unknown Title')
                        video_titles.append(title)
                else:
                    title = info_dict.get('title', 'Unknown Title')
                    video_titles.append(title)
        except Exception as e:
            self.log_output.emit(f"Error fetching video list: {str(e)}")

        self.video_titles.emit(video_titles)

    def run(self):
        self.fetch_video_list()

        self.log_output.emit(f"Starting download: {self.url}\n")

        ydl_opts = {
            'outtmpl': os.path.join(self.output_path, '%(title)s.%(ext)s'),
            'no_warnings': True,
            'quiet': True,
            'progress_hooks': [self.hook],
            'format': ('bestaudio' if self.format_option == 'Audio Only' else
                       'bestvideo' if self.format_option == 'Video Only' else
                       'best'),
            'merge_output_format': 'mp4',
            'ignoreerrors': True,
            'restrictfilenames': True,
            'noplaylist': not self.is_playlist,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
        except Exception as e:
            self.log_output.emit(f"Error: {str(e)}")

        self.finished.emit()
        self.log_output.emit("\n--- Download completed ---\n")


class MyLogger:
    def __init__(self, output_callback):
        self.output_callback = output_callback

    def debug(self, msg):
        self._log(msg)

    def warning(self, msg):
        self._log(f"[WARNING] {msg}")

    def error(self, msg):
        self._log(f"[ERROR] {msg}")

    def _log(self, msg):
        if msg.strip():
            self.output_callback(strip_ansi_escape(msg.strip()))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QuickYTDL")
        self.setGeometry(100, 100, 700, 500)

        #Set app icon
        icon_path = os.path.join(os.path.dirname(__file__), "resources", "QuickYTDL.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"[Warning] Icon not found at: {icon_path}")
        
        user_videos = os.path.join(os.path.expanduser("~"), "Videos", "YTDownload")
        os.makedirs(user_videos, exist_ok=True)
        self.output_directory = user_videos

        self._setup_ui()

    def _setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout(self.central_widget)

        layout.addWidget(QLabel("Video/Playlist URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter YouTube URL or Playlist URL")
        layout.addWidget(self.url_input)

        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Best", "Audio Only", "Video Only"])
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch()
        self.playlist_check = QCheckBox("Playlist")
        format_layout.addWidget(self.playlist_check)
        layout.addLayout(format_layout)

        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Save to:"))
        self.dir_label = QLabel(self.output_directory)
        self.dir_label.setMinimumWidth(300)
        dir_layout.addWidget(self.dir_label, 1)
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.browse_button)
        layout.addLayout(dir_layout)

        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.handle_download)
        layout.addWidget(self.download_button)

        layout.addWidget(QLabel("Video List:"))
        self.video_list = QPlainTextEdit()
        self.video_list.setReadOnly(True)
        #self.video_list.setStyleSheet("background-color: #111; color: #0f0; font-family: Consolas, monospace;")
        layout.addWidget(self.video_list)

        layout.addWidget(QLabel("Details:"))
        self.output_console = QPlainTextEdit()
        self.output_console.setReadOnly(True)
        #self.output_console.setStyleSheet("background-color: #111; color: #0f0; font-family: Consolas, monospace;")
        layout.addWidget(self.output_console)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("Progress: Waiting...")
        self.progress_label.setStyleSheet("color: #0f0; font-family: Consolas, monospace;")
        self.progress_label.setAlignment(Qt.AlignLeft)
        layout.addWidget(self.progress_label)

        #self.statusBar().showMessage("Ready")

    def browse_directory(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory")
        if folder:
            self.dir_label.setText(folder)
            self.output_directory = folder

    def handle_download(self):
        url = self.url_input.text().strip()
        format_option = self.format_combo.currentText()
        is_playlist = self.playlist_check.isChecked()
        output_path = self.output_directory

        if not url or not output_path:
            self.statusBar().showMessage("Please enter a URL and select a directory.", 5000)
            return

        self.output_console.clear()
        self.video_list.clear()
        #self.output_console.appendPlainText(f"Starting download: {url}")
        #self.statusBar().showMessage("Downloading...")
        self.progress_bar.setRange(0, 0)

        self.worker = DownloadWorker(url, output_path, format_option, is_playlist)
        self.worker.log_output.connect(self.output_console.appendPlainText)
        self.worker.video_titles.connect(self.display_video_list)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.finished.connect(lambda: self.statusBar().showMessage("Download finished", 5000))
        self.worker.finished.connect(lambda: self.progress_bar.setRange(0, 100))
        self.worker.finished.connect(lambda: self.progress_bar.setValue(100))
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def update_progress(self, percent, eta, speed):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percent)
        self.progress_label.setText(f"Progress: {percent}% ETA: {eta} Speed: {speed}")

    def display_video_list(self, video_list):
        self.video_list.clear()
        if video_list:
            self.video_list.appendPlainText("Videos to be downloaded:\n")
            for video in video_list:
                self.video_list.appendPlainText(f"- {video}")
            self.video_list.appendPlainText("\n--- Video List Fetched ---\n")
        else:
            self.video_list.appendPlainText("No videos found or failed to fetch the list.\n")
