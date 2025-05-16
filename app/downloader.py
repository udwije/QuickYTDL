"""QuickYTDL GUI for YouTube Video Downloader
This script provides a simple GUI for downloading YouTube videos using yt-dlp.
"""  
import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QMessageBox, QProgressBar, QPlainTextEdit, QCheckBox, QFileDialog, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QSize, QUrl, QEvent
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor
import re
import sys
import traceback
import yt_dlp  # ✅ Ensure yt_dlp is installed to fix E0401

def download_video(url, output_path, format_option, is_playlist, progress_callback=None):
    """Downloads a video or playlist using yt-dlp based on the provided options."""  

    format_map = {
        "Best": "best",
        "Audio Only": "bestaudio/best",
        "Video Only": "bestvideo/best",
    }

    ydl_opts = {
        'format': format_map.get(format_option, 'best'),
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'noplaylist': not is_playlist,
        'quiet': False,
        'progress_hooks': [progress_callback] if progress_callback else []
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True, "Download completed successfully."
    except yt_dlp.utils.DownloadError as e:  
        return False, f"Download error: {str(e)}"
    except Exception as e:  
        return False, f"An unexpected error occurred: {str(e)}"

