# quickytdl/utils.py

import os
import re
from datetime import timedelta, datetime
from pathlib import Path

def sanitize_filename(filename: str) -> str:
    """
    Strip out characters that are illegal in filenames on most filesystems.
    """
    return re.sub(r'[\\\/:*?"<>|]', "", filename)

def ensure_directory(path: str) -> None:
    """
    Create the directory (and parents) if it doesn't already exist,
    using pathlib for cross-platform reliability.
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[Utils] Error creating directory {path}: {e}")

def human_readable_size(num_bytes: int, suffix: str = "B") -> str:
    """
    Convert a byte count into a human-readable string, e.g. 1536000 -> '1.5MB'.
    """
    if num_bytes is None:
        return "0B"
    num = float(num_bytes)
    for unit in ["", "K", "M", "G", "T", "P"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Y{suffix}"

def format_duration(seconds: int) -> str:
    """
    Format a duration in seconds into HH:MM:SS.
    """
    return str(timedelta(seconds=int(seconds)))

def get_default_save_dir(app_name: str = "QuickYTDL") -> str:
    """
    Return a default save directory under the user's Videos folder,
    e.g. C:\\Users\\<User>\\Videos\\QuickYTDL Downloads.
    Falls back to a subfolder of the current working dir if creation fails.
    """
    try:
        home = os.path.expanduser("~")
        videos_dir = os.path.join(home, "Videos")
        default_dir = os.path.join(videos_dir, f"{app_name} Downloads")
        ensure_directory(default_dir)
        return default_dir
    except Exception as e:
        print(f"[Utils] Could not create default save dir: {e}")
        # fallback
        fallback = os.path.join(os.getcwd(), f"{app_name}_Downloads")
        ensure_directory(fallback)
        return fallback

def timestamped(message: str) -> str:
    """
    Prefix the given log message with a timestamp.
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{ts}] {message}"
