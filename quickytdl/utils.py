# quickytdl/utils.py

import os
import re
import sys
from datetime import timedelta, datetime
from pathlib import Path


def resource_path(*parts: str) -> str:
    """
    Resolve a path to a bundled resource (icon, image, etc.) that works both:
      - when running from source (python main.py), and
      - when frozen into a single-file PyInstaller .exe, where bundled
        data lives in a temp extraction dir exposed as sys._MEIPASS.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        # project root = one directory above this file's package (quickytdl/..)
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


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

    # 1) Ensure ~/Videos exists, then create ~/Videos/<app_name> Downloads
    videos_dir = os.path.join(home, "Videos")
    ensure_directory(videos_dir)   # will mkdir ~/Videos if needed
    candidate = os.path.join(videos_dir, f"{app_name} Downloads")
    ensure_directory(candidate)    # now mkdir the subfolder
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


# --------------------------------------------------------------------------
# yt-dlp JavaScript runtime support
# --------------------------------------------------------------------------

# Runtimes yt-dlp can drive, best first. Only 'deno' is enabled by default;
# the others work but must be switched on explicitly via the js_runtimes
# option, which is exactly what enabled_js_runtimes() below does.
#
# Background: since yt-dlp 2025.11.12, YouTube extraction without a JS
# runtime is deprecated. Without one, format availability is limited (and
# worsens over time), so higher resolutions can silently go missing.
#   deno     -> executable name 'deno'
#   node     -> executable name 'node'
#   bun      -> executable name 'bun'   (deprecated upstream)
#   quickjs  -> executable name 'qjs'
_JS_RUNTIME_EXES = (
    ("deno", "deno"),
    ("node", "node"),
    ("quickjs", "qjs"),
    ("bun", "bun"),
)


def find_js_runtime():
    """
    Return (runtime_name, executable_path) for the first available JS
    runtime, or (None, None) if none is installed.
    """
    import shutil
    for name, exe in _JS_RUNTIME_EXES:
        path = shutil.which(exe)
        if path:
            return name, path
    return None, None


def enabled_js_runtimes():
    """
    Value for yt-dlp's `js_runtimes` option.

    yt-dlp enables only deno by default, so a user with Node or QuickJS
    installed would still get the "no supported JavaScript runtime" warning
    and degraded formats. Explicitly enabling whatever we found avoids that.
    Returns None when nothing is installed, so the caller can leave the
    option alone.
    """
    name, path = find_js_runtime()
    if not name:
        return None
    return {name: {"path": path}}


def js_runtime_note():
    """
    One-line advisory to show at startup, or None when a runtime is present.
    """
    name, _ = find_js_runtime()
    if name:
        return None
    return (
        "⚠️ No JavaScript runtime found. YouTube may offer fewer formats, "
        "so higher resolutions can go missing. Install Deno to fix it — "
        "on Windows:  winget install --id=DenoLand.Deno"
    )
