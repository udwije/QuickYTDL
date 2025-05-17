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
    Create the directory (and parents) if it doesn't already exist.
    Uses pathlib for cross-platform reliability.
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        # We swallow the error so callers can fall back
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
    Return a default save directory:
      1) if ~/Videos exists, use ~/Videos/<app_name> Downloads
      2) else fall back to ~/<app_name> Downloads
      3) else fall back to ./<app_name>_Downloads
    """
    home = os.path.expanduser("~")

    # 1) Try ~/Videos
    videos_dir = os.path.join(home, "Videos")
    if os.path.isdir(videos_dir):
        candidate = os.path.join(videos_dir, f"{app_name} Downloads")
        ensure_directory(candidate)
        if os.path.isdir(candidate):
            return candidate

    # 2) Fallback to home folder
    candidate = os.path.join(home, f"{app_name} Downloads")
    ensure_directory(candidate)
    if os.path.isdir(candidate):
        return candidate

    # 3) Last‐ditch: project CWD
    candidate = os.path.join(os.getcwd(), f"{app_name}_Downloads")
    ensure_directory(candidate)
    return candidate

def timestamped(message: str) -> str:
    """
    Prefix the given log message with a timestamp.
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{ts}] {message}"
