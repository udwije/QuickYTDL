# quickytdl/fetcher.py

import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from PyQt6.QtCore import QObject, pyqtSignal
from yt_dlp import YoutubeDL

from quickytdl import formats
from quickytdl.utils import enabled_js_runtimes


_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


def _clean_error(msg) -> str:
    """Strip ANSI colour codes and yt-dlp's 'ERROR: ' prefix from a message."""
    text = _ANSI_RE.sub('', str(msg)).strip()
    if text.upper().startswith('ERROR:'):
        text = text[6:].strip()
    return text


def _nearest_tier(height: int):
    """
    Map a reported height onto the closest standard tier at or below it,
    so non-standard encodes still land in a bucket the UI offers.
    """
    for h in formats.VIDEO_HEIGHTS:          # descending
        if height >= h:
            return f"{h}p"
    return None


class VideoItem:
    """
    Represents a single video entry in a playlist.

    Attributes:
        index (int): 1-based position in the playlist.
        title (str): Video title (or fallback to ID).
        available_formats (list[str]): Resolutions like '1080p', plus 'mp3'.
        url (str): The video URL for downloading.
        source_url (str): The URL the user actually supplied. For a batch
            entry expanded out of a playlist this is the playlist URL, not
            the individual video — it's what groups rows together so the
            user can drop the rest of an unwanted playlist.
        source_title (str): Human label for that source (playlist title).
        from_playlist (bool): True when this row came from expanding a
            playlist rather than being a URL the user typed directly.
    """
    def __init__(self, index: int, title: str, available_formats: list[str], url: str,
                 source_url: str = None, source_title: str = None,
                 from_playlist: bool = False):
        self.index = index
        self.title = title
        self.available_formats = available_formats
        self.url = url
        self.source_url = source_url or url
        self.source_title = source_title or title
        self.from_playlist = from_playlist
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
            # 'in_playlist' (not True): flatten only the entries *inside* a
            # playlist, which keeps listing fast, but still fully resolve a
            # single-video URL so we get its real title. With True, yt-dlp
            # returns every URL as an unresolved stub and the UI ends up
            # showing the 11-char video ID as the description.
            'extract_flat': 'in_playlist',
            # yt-dlp colourises its error strings; those escape codes end up
            # as literal "[0;31m" junk in the log view.
            'no_color': True,
        }
        _js = enabled_js_runtimes()
        if _js:
            self.ydl_opts['js_runtimes'] = _js
        # Fallback tiers if no per-video heights are found.
        # playlist entries are flattened for speed, so they rarely carry a 'formats'
        # list and this fallback is the usual path.
        self.default_formats = list(formats.VIDEO_FORMATS)
        self.last_playlist_title = None

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    # Auto-generated list IDs that YouTube will not serve as a playlist.
    #   RD…   Mix / radio          RDMM… "My Mix"
    #   UL…   user list stub       LL    Liked videos (private)
    #   WL    Watch later (private)
    _UNLISTABLE_PREFIXES = ('RD', 'UL', 'LL', 'WL')

    @staticmethod
    def _video_id(url: str):
        """
        Pull an 11-character YouTube video ID out of a URL, or None.
        Handles watch?v=, youtu.be/, /shorts/, /embed/ and /live/.
        """
        if not url:
            return None
        try:
            parsed = urlparse(url)
        except Exception:
            return None

        vid = parse_qs(parsed.query).get('v', [None])[0]
        if not vid:
            host = (parsed.netloc or '').lower()
            path = (parsed.path or '').strip('/')
            segments = path.split('/')
            if 'youtu.be' in host:
                vid = segments[0] if segments else None
            elif segments and segments[0] in ('shorts', 'embed', 'live', 'v'):
                vid = segments[1] if len(segments) > 1 else None

        if vid and re.fullmatch(r'[0-9A-Za-z_-]{11}', vid):
            return vid
        return None

    @classmethod
    def _is_unlistable_playlist(cls, url: str) -> bool:
        """
        True when the ?list= param names a playlist YouTube generates on the
        fly (Mix/radio, Liked, Watch later). These cannot be enumerated, so
        we should go straight to the single video.
        """
        try:
            list_id = parse_qs(urlparse(url or '').query).get('list', [None])[0]
        except Exception:
            return False
        if not list_id:
            return False
        return list_id.upper().startswith(cls._UNLISTABLE_PREFIXES)

    # ------------------------------------------------------------------
    # Shared entry -> VideoItem conversion
    # ------------------------------------------------------------------

    def _build_item(self, entry: dict, index: int,
                    source_url: str = None, source_title: str = None,
                    from_playlist: bool = False) -> VideoItem | None:
        """
        Turn a single yt-dlp entry into a VideoItem.

        Shared by fetch_playlist() and fetch_urls() so both paths produce
        identical format lists. `index` is 1-based and is used both for the
        "Video No" column and the NNN- filename prefix, so callers must
        assign it across the whole batch, not per source URL.
        """
        if entry is None:
            return None

        title = entry.get('title') or entry.get('id') or f"Video #{index}"

        # Build available_formats: look for video heights.
        # Do NOT filter on ext == 'mp4' here. YouTube publishes nothing
        # above 1080p as MP4 — 1440p/2160p/4320p are VP9 or AV1 in WebM
        # — so an MP4-only scan silently caps the list at 1080p. Accept
        # any stream that carries a real video track instead, and let
        # the container get decided at download time.
        fmts = entry.get('formats') if isinstance(entry.get('formats'), list) else None
        heights = set()
        if fmts:
            for f in fmts:
                h = f.get('height')
                if h and f.get('vcodec') not in (None, 'none'):
                    heights.add(f"{h}p")
            # Snap odd heights (e.g. 1082) onto the nearest standard tier
            # so the combo never shows resolutions the UI can't request.
            heights = {
                t for t in (
                    _nearest_tier(int(s.rstrip('p'))) for s in heights
                ) if t
            }
        if not heights:
            heights = set(self.default_formats)

        # 'best' first, then descending resolution, MP3 last.
        available_formats = formats.sorted_formats(
            {formats.BEST} | heights | {formats.MP3}
        )

        video_url = entry.get('webpage_url') or entry.get('id')
        return VideoItem(
            index, title, available_formats, video_url,
            source_url=source_url or video_url,
            source_title=source_title or title,
            from_playlist=from_playlist,
        )

    def _extract(self, url: str, want_playlist: bool = True):
        """
        Flat-extract a single URL.

        Returns (entries, is_playlist, source_title). A bare video yields a
        single-entry list with is_playlist False; a playlist yields all of
        its entries with is_playlist True, so the UI can group the rows and
        let the user drop a playlist they didn't mean to expand.

        want_playlist=False forces yt-dlp to ignore any ?list= param and
        resolve only the video itself.

        Robustness: many YouTube URLs carry a ?list= that points at a
        *generated* playlist — Mixes/radio (RD…), "my mix" (RDMM…), likes
        (LL), watch-later (WL). Those are not listable and yt-dlp errors
        with e.g. "This playlist type is unviewable", which used to fail
        the whole URL even though the video ID in it is perfectly good.
        We now fall back to the bare video instead of losing the row.

        Raises only when even the bare video cannot be resolved, so callers
        can still treat that as a genuine failure.
        """
        video_id = self._video_id(url)

        # A generated/unviewable list is never worth trying to expand.
        if want_playlist and self._is_unlistable_playlist(url) and video_id:
            want_playlist = False

        opts = dict(self.ydl_opts)
        if not want_playlist:
            opts['noplaylist'] = True

        def run(target, o):
            with YoutubeDL(o) as ydl:
                return ydl.extract_info(target, download=False)

        try:
            info = run(url, opts)
        except Exception:
            # Playlist resolution blew up. If the URL still identifies a
            # single video, salvage it rather than dropping the row.
            if not video_id:
                raise
            fallback = dict(self.ydl_opts)
            fallback['noplaylist'] = True
            info = run(f"https://www.youtube.com/watch?v={video_id}", fallback)
            entries = [e for e in ([info]) if e is not None]
            title = info.get('title') or url
            self.log.emit(
                f"      ↳ playlist unavailable; using the single video instead"
            )
            return entries, False, title

        entries = info.get('entries') or []
        is_playlist = bool(entries)

        if not entries:
            parsed = urlparse(url)
            list_id = parse_qs(parsed.query).get('list', [None])[0]
            if list_id and want_playlist and not self._is_unlistable_playlist(url):
                playlist_url = f"https://www.youtube.com/playlist?list={list_id}"
                try:
                    info2 = run(playlist_url, opts)
                    entries = info2.get('entries') or []
                    is_playlist = bool(entries)
                    if entries:
                        info = info2
                except Exception:
                    # Keep whatever the first pass gave us.
                    pass
            if not entries:
                # Plain single video.
                entries = [info]
                is_playlist = False

        entries = [e for e in entries if e is not None]

        # A "playlist" that resolved to exactly one video is not worth
        # grouping — treat it as a single video.
        if len(entries) <= 1:
            is_playlist = False

        title = info.get('title') or info.get('playlist_title') or url
        return entries, is_playlist, title

    def fetch_urls(self, urls: list[str], max_workers: int = 5,
                   expand_playlists: bool = True,
                   preselect_playlists: bool = True) -> list[VideoItem]:
        """
        Fetch metadata for an arbitrary list of URLs (batch mode).

        Unlike fetch_playlist(), the URLs are unrelated: each is extracted
        independently and the results are concatenated into one list.

        Behaviour that matters:
          * URLs are fetched concurrently — serial extraction of 30 URLs
            would freeze the fetch step for ~30s.
          * A URL that fails is logged and skipped; it never aborts the
            batch. Private/deleted videos are common in pasted lists.
          * Duplicates are removed, preserving first-seen order.
          * A pasted playlist URL is expanded inline, since that costs
            nothing and matches what users expect.
          * Indices are assigned sequentially across the whole batch so
            the NNN- filename prefixes never collide.

        Playlist handling:
          * expand_playlists=False keeps only the first video of any URL
            that turns out to be a playlist, for users who pasted a watch
            URL that happened to carry a ?list= param.
          * preselect_playlists=False leaves playlist-expanded rows
            unticked, so a 200-video playlist never downloads by accident;
            the user opts in per row (or via the source context menu).
          Rows carry source_url/source_title/from_playlist so the UI can
          group them.
        """
        from concurrent.futures import ThreadPoolExecutor

        # Dedupe, preserve order.
        seen = set()
        ordered: list[str] = []
        for u in urls:
            u = (u or "").strip()
            if u and u not in seen:
                seen.add(u)
                ordered.append(u)

        if not ordered:
            self.log.emit("⚠️ No valid URLs provided.")
            self.last_playlist_title = None
            return []

        total = len(ordered)
        dropped = len(urls) - total
        if dropped > 0:
            self.log.emit(f"🔍 {total} unique URL(s) to fetch ({dropped} duplicate/blank removed).")
        else:
            self.log.emit(f"🔍 {total} URL(s) to fetch.")

        # Extract concurrently, but keep results in input order.
        results: list[list[dict] | None] = [None] * total
        errors: list[tuple[str, str]] = []

        def work(i_url):
            i, u = i_url
            try:
                return i, self._extract(u, want_playlist=expand_playlists), None
            except Exception as e:                       # noqa: BLE001
                return i, None, _clean_error(e)

        workers = max(1, min(max_workers, total))
        playlist_sources = []          # (url, title, count) for the summary
        with ThreadPoolExecutor(max_workers=workers) as pool:
            done = 0
            for i, payload, err in pool.map(work, enumerate(ordered)):
                done += 1
                url = ordered[i]
                if err is not None:
                    errors.append((url, err))
                    self.log.emit(f"  ❌ [{done}/{total}] Failed: {url}\n      {err}")
                    continue

                entries, is_playlist, src_title = payload
                # A "playlist" holding a single video isn't worth grouping;
                # enforce here as well as in _extract so the rule holds no
                # matter which extraction path produced the payload.
                if is_playlist and len(entries) <= 1:
                    is_playlist = False
                if is_playlist and not expand_playlists:
                    # noplaylist should already have prevented this; guard anyway.
                    entries = entries[:1]
                    is_playlist = False
                    self.log.emit(
                        f"  • [{done}/{total}] Playlist collapsed to first video: {src_title}"
                    )
                elif is_playlist:
                    playlist_sources.append((url, src_title, len(entries)))
                    self.log.emit(
                        f"  ⚠️ [{done}/{total}] '{src_title}' is a PLAYLIST — "
                        f"{len(entries)} videos from: {url}"
                    )
                else:
                    label = entries[0].get('title') if entries else url
                    self.log.emit(f"  • [{done}/{total}] {label}")

                results[i] = (entries, is_playlist, src_title)

        # Flatten in input order, numbering across the whole batch.
        items: list[VideoItem] = []
        for idx, payload in enumerate(results):
            if not payload:
                continue
            entries, is_playlist, src_title = payload
            src_url = ordered[idx]
            for entry in entries:
                item = self._build_item(
                    entry, len(items) + 1,
                    source_url=src_url,
                    source_title=src_title if is_playlist else None,
                    from_playlist=is_playlist,
                )
                if item is None:
                    continue
                # Playlist rows can start unticked so a large playlist is
                # never downloaded by accident.
                item.selected = True if not is_playlist else bool(preselect_playlists)
                items.append(item)

        # No playlist title exists for a batch, so give the UI a stable
        # date-stamped folder name instead of leaving it blank (which would
        # dump every file into the save-path root).
        self.last_playlist_title = f"Batch {datetime.now():%Y-%m-%d}"

        if playlist_sources:
            self.log.emit(
                f"\n📋 {len(playlist_sources)} of your URL(s) expanded into playlists:"
            )
            for url, title, count in playlist_sources:
                self.log.emit(f"  • '{title}' → {count} videos")
            self.log.emit(
                "  Right-click any row to select/deselect a whole source, "
                "or untick rows you don't want."
            )

        if errors:
            self.log.emit(
                f"\n✅ Completed metadata for {len(items)} video(s); "
                f"{len(errors)} URL(s) failed:"
            )
            for url, err in errors:
                self.log.emit(f"  ❌ {url}")
        else:
            self.log.emit(f"\n✅ Completed metadata for {len(items)} video(s).\n")

        return items

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
        # If no playlist entries and no ?list=… param, treat as a single‐video playlist
        if not entries and list_id is None:
            entries = [info]

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

            title = entry.get('title') or entry.get('id') or f"Video #{i}"
            self.log.emit(f"  • Processing [{i}/{total}]: {title}")

            item = self._build_item(entry, len(items) + 1)
            if item is None:
                continue
            items.append(item)
            self.log.emit(f"    – Formats: {', '.join(item.available_formats)}")

        self.log.emit(f"✅ Completed metadata for {len(items)} videos.\n")
        return items
