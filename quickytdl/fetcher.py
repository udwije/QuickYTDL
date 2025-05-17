# quickytdl/fetcher.py
import re
from PyQt6.QtCore import QObject, pyqtSignal
from yt_dlp import YoutubeDL


class VideoItem:
    """
    Represents a single video entry in a playlist.

    Attributes:
        index (int): 1-based position in the playlist.
        title (str): Video title (or fallback to ID).
        available_formats (list[str]): List of resolution strings (e.g. '1080p').
        url (str): The video URL for downloading.
    """
    def __init__(self, index: int, title: str, available_formats: list[str], url: str):
        self.index = index
        self.title = title
        self.available_formats = available_formats
        self.url = url
        # The following fields are managed by the table models:
        # self.selected, self.selected_format, self.progress, self.status


class PlaylistFetcher(QObject):
    """
    Fetches playlist metadata via yt-dlp.
    Emits log messages so the UI can display progress and status.

    Uses the "flat" extractor to list titles and URLs quickly,
    then provides a fixed set of common resolutions for selection.
    """
    log = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # yt-dlp options: no download, minimal output, flat list
        self.ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'no_warnings': True,
            #'extract_flat': 'in_playlist',  # list entries without full metadata
            'extract_flat': True,  # list entries without full metadata
        }
        # default fallback formats if detailed formats unavailable
        self.default_formats = ["1080p", "720p", "480p", "360p"]
        # will hold last playlist title
        self.last_playlist_title = None

    def fetch_playlist(self, url: str) -> list[VideoItem]:
        """
        Retrieves the playlist entries for the given URL.

        Returns:
            list[VideoItem]: A list of VideoItem with index, title,
                             available_formats, and URL.
        """
        self.log.emit(f"🔍 Starting metadata extraction for:\n{url}")

        try:
            with YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            self.log.emit(f"❌ Failed to fetch metadata: {e}")
            return []
        # capture and sanitize playlist title
        raw_title = info.get("title") or "Playlist"
        # truncate to 20 chars, with ellipsis if needed
        safe = re.sub(r'[\\\/:*?"<>|]', "", raw_title)
        if len(safe) > 20:
            safe = safe[:19] + "…"
        self.last_playlist_title = safe

        entries = info.get('entries') or []
        total = len(entries)
        self.log.emit(f"🔎 Found {total} videos in playlist.")

        items: list[VideoItem] = []
        for i, entry in enumerate(entries, start=1):
            if entry is None:
                self.log.emit(f"  ⚠️ Skipping empty entry at position {i}")
                continue

            # Title fallback: use ID if title missing
            title = entry.get('title') or entry.get('id') or f"Video #{i}"
            self.log.emit(f"  • Processing [{i}/{total}]: {title}")

            # Determine available formats if provided, else fallback
            formats = entry.get('formats', None)
            if formats and isinstance(formats, list):
                # extract unique heights, e.g. 1080p, 720p
                heights = {
                    f"{fmt['height']}p"
                    for fmt in formats
                    if fmt.get('height') is not None
                }
                available_formats = sorted(
                    heights,
                    key=lambda s: int(s.rstrip('p')),
                    reverse=True
                )
                if not available_formats:
                    self.log.emit("    – No video formats found, using defaults.")
                    available_formats = self.default_formats.copy()
            else:
                # flat extractor does not include formats
                available_formats = self.default_formats.copy()
                self.log.emit("    – Using default format list.")

            # Pick the best URL field for download
            video_url = entry.get('webpage_url') or entry.get('id')
            item = VideoItem(i, title, available_formats, video_url)
            items.append(item)

            self.log.emit(
                f"    – Formats: {', '.join(available_formats)}"
            )

        self.log.emit(f"✅ Completed metadata for {len(items)} videos.\n")
        return items
