import yt_dlp

def download_video(url, output_path, format_option, is_playlist, progress_callback=None):
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
    except Exception as e:
        return False, f"An error occurred: {str(e)}"