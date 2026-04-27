"""Robust audio loading utility.

torchaudio 2.9+ uses torchcodec exclusively and does not apply FFmpeg's
error-recovery flags, so certain MP3s (VBR, non-standard headers, iPhone
Voice Memos) that the FFmpeg CLI handles fine will raise a RuntimeError.

All audio loading in the project should go through load_audio() to get
automatic fallback to FFmpeg subprocess when torchcodec fails.
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio

logger = logging.getLogger(__name__)


def load_audio(path: str | Path) -> tuple[torch.Tensor, int]:
    """Load audio with automatic FFmpeg fallback.

    Returns:
        Tuple of (waveform tensor [channels, samples], sample_rate).
    """
    path = str(path)

    try:
        waveform, sr = torchaudio.load(path)
        return waveform, sr
    except RuntimeError as e:
        if "Failed to decode audio" not in str(e) and "Could not open input" not in str(e):
            raise
        logger.warning(
            f"torchcodec failed to load {path!r} ({e}), "
            "falling back to FFmpeg subprocess"
        )

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-fflags", "+discardcorrupt",
                "-err_detect", "ignore_err",
                "-i", path,
                tmp_path,
            ],
            check=True,
            timeout=120,
        )
        data, sr = sf.read(tmp_path)
        if data.ndim == 1:
            data = data[:, np.newaxis]
        waveform = torch.from_numpy(data.T.astype(np.float32))
        return waveform, sr
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def validate_ffmpeg() -> None:
    """Check that FFmpeg is installed and callable. Raises RuntimeError if not."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        version_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
        logger.info(f"FFmpeg available: {version_line}")
    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg is not installed or not on PATH. "
            "FFmpeg is required for robust audio decoding. "
            "Install with: brew install ffmpeg"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("FFmpeg timed out during version check")
