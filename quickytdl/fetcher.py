# quickytdl/fetcher.py

from PyQt6.QtCore import QObject, pyqtSignal
from yt_dlp import YoutubeDL


class VideoItem:
    """
    Simple container for a single video entry in a playlist.
    Attributes populated by PlaylistFetcher.fetch_playlist().
    """
    def __init__(self, index: int, title: str, available_formats: list[str]):
        self.index = index
        self.title = title
        self.available_formats = available_formats
        # The following will be managed by the table models:
        # self.selected: bool
        # self.selected_format: str
        # self.progress: float
        # self.status: str


class PlaylistFetcher(QObject):
    """
    Uses yt-dlp to extract playlist info and emits log messages.
    """
    log = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # yt-dlp options to suppress output and skip actual download
        self.ydl_opts = {
            'quiet': True,
            'skip_download': True,
            # we want full format list in entry['formats']
            'no_warnings': True,
        }

    def fetch_playlist(self, url: str) -> list[VideoItem]:
        """
        Given a YouTube playlist URL, returns a list of VideoItem
        with index, title, and available_formats (e.g. ["1080p","720p",...]).
        Emits log messages via the `log` signal.
        """
        self.log.emit(f"Fetching playlist: {url}")
        items: list[VideoItem] = []
        try:
            with YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            self.log.emit(f"❌ Error fetching playlist: {e}")
            return items

        entries = info.get('entries') or []
        for i, entry in enumerate(entries, start=1):
            title = entry.get('title') or entry.get('id') or f"Video #{i}"
            # Collect unique heights from available formats
            formats = entry.get('formats', [])
            heights = {
                f"{fmt['height']}p"
                for fmt in formats
                if fmt.get('height') is not None
            }
            # Sort by numeric value descending (1080p, 720p, ...)
            available_formats = sorted(
                heights,
                key=lambda s: int(s.rstrip('p')),
                reverse=True
            )
            item = VideoItem(i, title, available_formats)
            items.append(item)
            self.log.emit(
                f"  • [{i}] {title} — formats: {', '.join(available_formats) or 'none'}"
            )

        self.log.emit(f"✅ Fetched {len(items)} videos.")
        return items
