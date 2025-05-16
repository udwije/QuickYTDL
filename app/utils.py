# =========================
# app/utils.py
# =========================

def sanitize_metadata(data):
    return data

def format_emoji(status):
    emojis = {
        'queued': '⏳',
        'complete': '✅',
        'error': '❌'
    }
    return emojis.get(status.lower(), '')

def get_format_options():
    return [
        "360p",
        "480p",
        "720p",
        "1080p",
        "Audio Only",
    ]
