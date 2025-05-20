# quickytdl/fetcher.py

import re
from urllib.parse import urlparse, parse_qs
from PyQt6.QtCore import QObject, pyqtSignal
from yt_dlp import YoutubeDL


class VideoItem:
    """
    Represents a single video entry in a playlist.

    Attributes:
        index (int): 1-based position in the playlist.
        title (str): Video title (or fallback to ID).
        available_formats (list[str]): Resolutions like '1080p', plus 'mp3'.
        url (str): The video URL for downloading.
    """
    def __init__(self, index: int, title: str, available_formats: list[str], url: str):
        self.index = index
        self.title = title
        self.available_formats = available_formats
        self.url = url
        # The following are set by the UI/models:
        # self.selected, self.selected_format, self.progress, self.status, self.sample_rate


class PlaylistFetcher(QObject):
    """
    Fetches playlist metadata via yt-dlp.
    Emits log messages so the UI can display progress and status.

    Uses the "flat" extractor for speed, then offers a fixed list
    of MP4 resolutions plus MP3 audio.
    """
    log = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # Fast, flat listing (no full metadata download)
        self.ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        # Fallback formats if no MP4 heights are found
        self.default_formats = ["1080p", "720p", "480p", "360p"]
        self.last_playlist_title = None

    def fetch_playlist(self, url: str) -> list[VideoItem]:
        """
        Retrieve playlist entries for the given URL.
        Returns a list of VideoItem.
        """
        self.log.emit(f"🔍 Starting metadata extraction for:\n{url}")

        # Extract 'list' param if present (for watch URLs)
        parsed = urlparse(url)
        list_id = parse_qs(parsed.query).get('list', [None])[0]

        # 1) Initial flat extract
        try:
            with YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            self.log.emit(f"❌ Failed to fetch metadata: {e}")
            return []

        entries = info.get('entries') or []

        # 2) If no entries but we have a list_id, re-fetch the actual playlist
        if not entries and list_id:
            playlist_url = f"https://www.youtube.com/playlist?list={list_id}"
            self.log.emit(f"🔍 Re-fetching full playlist metadata for:\n{playlist_url}")
            try:
                with YoutubeDL(self.ydl_opts) as ydl2:
                    info = ydl2.extract_info(playlist_url, download=False)
            except Exception as e:
                self.log.emit(f"❌ Failed to fetch playlist: {e}")
                return []
            entries = info.get('entries') or []

        # 3) Determine playlist title
        raw_title = info.get("title") or info.get("playlist_title") or "Playlist"
        safe = re.sub(r'[\\\/:*?"<>|]', "", raw_title)
        if len(safe) > 20:
            safe = safe[:19] + "…"
        self.last_playlist_title = safe

        total = len(entries)
        self.log.emit(f"🔎 Found {total} videos in playlist.")

        items: list[VideoItem] = []
        for i, entry in enumerate(entries, start=1):
            if entry is None:
                self.log.emit(f"  ⚠️ Skipping empty entry at position {i}")
                continue

            # Title (fallback to ID)
            title = entry.get('title') or entry.get('id') or f"Video #{i}"
            self.log.emit(f"  • Processing [{i}/{total}]: {title}")

            # Build available_formats: look for MP4 heights
            fmts = entry.get('formats') if isinstance(entry.get('formats'), list) else None
            heights = set()
            if fmts:
                for f in fmts:
                    h = f.get('height')
                    if h and f.get('ext') == 'mp4':
                        heights.add(f"{h}p")
            if not heights:
                self.log.emit("    – No MP4 formats found, using defaults.")
                heights = set(self.default_formats)

            available_formats = sorted(
                heights,
                key=lambda s: int(s.rstrip('p')),
                reverse=True
            )

            # Always allow MP3
            if "mp3" not in available_formats:
                available_formats.append("mp3")

            video_url = entry.get('webpage_url') or entry.get('id')
            items.append(VideoItem(i, title, available_formats, video_url))
            self.log.emit(f"    – Formats: {', '.join(available_formats)}")

        self.log.emit(f"✅ Completed metadata for {len(items)} videos.\n")
        return items
