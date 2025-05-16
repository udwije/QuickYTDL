import yt_dlp
from app.signals import AppSignals

class Fetcher:
    def __init__(self, signals: AppSignals):
        self.signals = signals

    def fetch_playlist_metadata(self, url):
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'ignoreerrors': True,
            'extract_flat': True,  # to get video info without downloading
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        videos = []
        if 'entries' in info:
            for video in info['entries']:
                if video is None:
                    continue
                videos.append({
                    "title": video.get('title', 'Unknown Title'),
                    "duration": video.get('duration', 0),
                    "url": video.get('url'),
                    "selected": True,
                    "status": "⏳"
                })
        else:
            # Single video, no playlist
            videos.append({
                "title": info.get('title', 'Unknown Title'),
                "duration": info.get('duration', 0),
                "url": info.get('url'),
                "selected": True,
                "status": "⏳"
            })

        return videos
