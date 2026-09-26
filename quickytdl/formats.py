# quickytdl/formats.py

"""
Single source of truth for download quality tiers.

Format identifiers are plain strings ("2160p", "mp3", "best") so they stay
compatible with everything that already passes them around as text:
VideoItem.available_formats, PlaylistTableModel edit values,
FormatDelegate's per-row combo, and DownloadWorker.selected_format.

Container rule
--------------
YouTube only publishes H.264/MP4 up to 1080p. Everything above that is VP9
or AV1 in WebM, so an MP4 container cannot hold it. Tiers above 1080p (and
"best") therefore merge into MKV, which takes VP9/AV1/Opus as a straight
remux with no re-encode. 1080p and below keep merging to MP4 exactly as
before.
"""

BEST = "best"
MP3 = "mp3"

# Descending, highest first.
VIDEO_HEIGHTS = [4320, 2160, 1440, 1080, 720, 480, 360]

VIDEO_FORMATS = [f"{h}p" for h in VIDEO_HEIGHTS]

# Order used to populate the global combo and per-row combos.
ALL_FORMATS = [BEST] + VIDEO_FORMATS + [MP3]

# Highest resolution that YouTube still ships as MP4/H.264.
MP4_MAX_HEIGHT = 1080


def height_of(fmt: str):
    """
    Return the integer height for a video tier, or None for 'best'/'mp3'
    and anything unrecognised.
    """
    if not fmt or fmt in (BEST, MP3):
        return None
    try:
        return int(str(fmt).rstrip("p"))
    except (ValueError, AttributeError):
        return None


def is_video(fmt: str) -> bool:
    """True for a real video tier or 'best'; False for 'mp3'."""
    return fmt != MP3 and (fmt == BEST or height_of(fmt) is not None)


def needs_mkv(fmt: str) -> bool:
    """
    True when the tier cannot be delivered in an MP4 container.
    'best' counts, because it may resolve to a 4K VP9/AV1 stream.
    """
    if fmt == BEST:
        return True
    h = height_of(fmt)
    return h is not None and h > MP4_MAX_HEIGHT


def container_for(fmt: str) -> str:
    return "mkv" if needs_mkv(fmt) else "mp4"


def sort_key(fmt: str):
    """
    Sort helper that tolerates the non-numeric tiers:
    'best' first, then descending height, 'mp3' last.
    """
    if fmt == BEST:
        return (0, 0)
    if fmt == MP3:
        return (2, 0)
    return (1, -(height_of(fmt) or 0))


def sorted_formats(fmts) -> list:
    """Order an arbitrary collection of tier strings for display."""
    return sorted(set(fmts), key=sort_key)


def build_format_opts(fmt: str) -> dict:
    """
    Build the format-related slice of yt-dlp options for a tier.

    Returns only 'format', 'format_sort' and 'merge_output_format' so the
    caller can merge it into its own opts without clobbering outtmpl,
    ffmpeg_location, progress_hooks, etc.

    Uses format_sort rather than a hard height filter. 'res:2160' picks the
    best stream at or below 2160p and only reaches upward if nothing at or
    below exists, so a playlist item that tops out at 720p degrades quietly
    instead of raising "Requested format is not available".
    """
    if fmt == MP3:
        return {"format": "bestaudio/best"}

    # Anything unrecognised (None, a stale config value) is treated as
    # 'best' rather than falling through to an MP4 container it may not fit.
    if fmt not in ALL_FORMATS:
        fmt = BEST

    opts = {"format": "bv*+ba/b"}
    height = height_of(fmt)

    if fmt == BEST or height is None:
        opts["format_sort"] = ["res", "fps"]
    elif height > MP4_MAX_HEIGHT:
        opts["format_sort"] = [f"res:{height}", "fps"]
    else:
        # At 1080p and below prefer the MP4/M4A pair so the merge into an
        # MP4 container stays a remux. This is a preference, not a filter:
        # if no MP4 exists the download still succeeds.
        opts["format_sort"] = [f"res:{height}", "ext:mp4:m4a", "fps"]

    opts["merge_output_format"] = container_for(fmt)
    return opts
