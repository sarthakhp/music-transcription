"""YouTube (and any yt-dlp supported URL) audio downloader."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

MAX_DURATION_SECONDS = 600  # 10 minutes


@dataclass
class VideoMetadata:
    title: str
    duration: float          # seconds
    uploader: str
    url: str
    thumbnail: Optional[str] = None


class UnsupportedURLError(Exception):
    pass


class VideoDurationError(Exception):
    pass


def fetch_metadata(url: str, check_duration: bool = True) -> VideoMetadata:
    """Fetch video metadata without downloading anything.

    Args:
        url: Any URL supported by yt-dlp.
        check_duration: If True, raise VideoDurationError for videos longer
            than MAX_DURATION_SECONDS. Pass False for the preview/metadata
            endpoint where the user hasn't trimmed yet — they need to see the
            full duration so they can decide how to trim it.

    Raises:
        UnsupportedURLError: if yt-dlp can't handle the URL.
        VideoDurationError: if check_duration=True and video exceeds limit.
    """
    import yt_dlp

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise UnsupportedURLError(f"Could not fetch video info: {e}") from e

    duration = info.get("duration") or 0

    if check_duration and duration > MAX_DURATION_SECONDS:
        raise VideoDurationError(
            f"Video is {duration:.0f}s — maximum allowed is {MAX_DURATION_SECONDS}s "
            f"({MAX_DURATION_SECONDS // 60} minutes). Use the trim handles to select "
            f"a shorter section."
        )

    title = info.get("title", "audio") or "audio"

    return VideoMetadata(
        title=title,
        duration=float(duration),
        uploader=info.get("uploader") or info.get("channel") or "unknown",
        url=url,
        thumbnail=info.get("thumbnail"),
    )


def download_audio(
    url: str,
    output_dir: Path,
    progress_callback: Optional[Callable[[int, str], None]] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
) -> Path:
    """Download audio from URL and save as MP3 in output_dir.

    Args:
        url: Any URL supported by yt-dlp.
        output_dir: Directory to save the audio file.
        progress_callback: Called with (pct 0-100, message) during download.
        start_time: Optional start offset in seconds (requires ffmpeg).
        end_time: Optional end offset in seconds (requires ffmpeg).

    Returns:
        Path to the downloaded MP3 file.

    Raises:
        UnsupportedURLError: if yt-dlp can't download the URL.
    """
    import yt_dlp

    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded_path: list[Path] = []  # mutable container for closure

    def _progress_hook(d: dict):
        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            pct = min(90, int(downloaded / total * 90))
            eta = d.get("_eta_str", "")
            speed = d.get("_speed_str", "")
            msg = f"Downloading audio {d.get('_percent_str', '')} — {speed} ETA {eta}"
            if progress_callback:
                progress_callback(pct, msg.strip(" —"))
        elif d["status"] == "finished":
            if progress_callback:
                progress_callback(95, "Processing downloaded audio")

    postprocessors = [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "0",
        }
    ]

    # Trim to requested time range
    if start_time is not None or end_time is not None:
        postprocessors.append({
            "key": "FFmpegTrimAudio",
            "start_time": start_time,
            "end_time": end_time,
        })

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "%(title)s.%(ext)s"),
        "postprocessors": postprocessors,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_progress_hook],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # yt-dlp renames the file after postprocessing; find the mp3
            title = yt_dlp.utils.sanitize_filename(info.get("title", "audio"))
            mp3_path = output_dir / f"{title}.mp3"
            downloaded_path.append(mp3_path)
    except yt_dlp.utils.DownloadError as e:
        raise UnsupportedURLError(f"Download failed: {e}") from e

    # yt-dlp may produce a slightly different filename — scan for any mp3
    if not mp3_path.exists():
        mp3_files = list(output_dir.glob("*.mp3"))
        if not mp3_files:
            raise UnsupportedURLError("Download completed but no MP3 file found")
        mp3_path = mp3_files[0]

    if progress_callback:
        progress_callback(100, f"Downloaded: {mp3_path.name}")

    logger.info(f"Audio downloaded: {mp3_path} ({mp3_path.stat().st_size // 1024}KB)")
    return mp3_path
