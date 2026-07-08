"""Audio source separator using configurable models via audio_separator.

Each subprocess creates its own Separator instance with the desired model.
The model file is downloaded once (via `download_model_if_needed`) and then
loaded from disk cache on each subsequent use (~2-3s).
"""

import logging
import threading
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import torch
import torchaudio

from src.audio_io import load_audio
from .config import SeparationConfig
from .memory import clear_memory
from .chunk_merger import merge_chunks
from .audio_processing import process_chunk

logger = logging.getLogger(__name__)

_separation_lock = threading.Lock()


def download_model_if_needed(
    config: SeparationConfig,
    progress_callback: Optional[Callable[[int, str], None]] = None,
) -> None:
    """Ensure the model file is downloaded to disk cache.

    Safe to call multiple times — audio_separator skips the download
    if the file already exists. Call this early (e.g. subprocess startup)
    so that separation itself is a fast disk read.

    If progress_callback is given, it receives (percent, message) updates
    while the ~600MB model downloads. audio_separator reports download
    progress via a plain tqdm instance instantiated inside its own
    download_file_if_not_exists(); there's no hook for it, so we swap the
    module's `tqdm` reference for a subclass that forwards updates to the
    callback, then restore it. If the model is already cached, the download
    is skipped entirely and only the 0%/100% bookend calls fire.
    """
    from audio_separator.separator import Separator

    logger.info(f"Ensuring model is cached: {config.model_filename} (key={config.model_key})")
    sep = Separator(
        output_dir=str(config.output_dir),
        output_format=config.output_format,
    )

    if progress_callback is None:
        sep.load_model(model_filename=config.model_filename)
        logger.info(f"Model ready: {config.model_filename}")
        return

    import audio_separator.separator.separator as _as_separator_module

    last_pct = -1

    def _report(pct: int) -> None:
        nonlocal last_pct
        if pct != last_pct:
            last_pct = pct
            progress_callback(pct, f"Downloading separation model ({pct}%)")

    base_tqdm = _as_separator_module.tqdm

    class _ProgressTqdm(base_tqdm):
        def update(self, n=1):
            result = super().update(n)
            if self.total:
                _report(int(min(self.n, self.total) / self.total * 100))
            return result

    progress_callback(0, "Preparing separation model")
    _as_separator_module.tqdm = _ProgressTqdm
    try:
        sep.load_model(model_filename=config.model_filename)
    finally:
        _as_separator_module.tqdm = base_tqdm

    progress_callback(100, "Separation model ready")
    logger.info(f"Model ready: {config.model_filename}")


class AudioSeparator:
    """Separates audio into stems using a configured model.

    Stateless per-job: create one instance per job with the right config,
    call `separate()`, then discard.
    """

    def __init__(self, config: SeparationConfig):
        self.config = config
        self.device = config.get_device()

        if config.seed is not None:
            torch.manual_seed(config.seed)
            if self.device == "mps":
                torch.mps.manual_seed(config.seed)

        logger.info(
            f"AudioSeparator initialized: model={config.model_key}, "
            f"device={self.device}, stems={config.stems}"
        )

    def _create_separator(self, output_dir: Path):
        """Create a fresh audio_separator.Separator pointed at output_dir.

        The model file is already on disk from download_model_if_needed(),
        so load_model() is a fast disk read.
        """
        from audio_separator.separator import Separator

        separator = Separator(
            output_dir=str(output_dir),
            output_format=self.config.output_format,
        )
        separator.load_model(model_filename=self.config.model_filename)
        return separator

    def separate(
        self,
        audio_path: str | Path,
        output_dir: str | Path,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> dict[str, np.ndarray]:
        """Separate audio into stems.

        Args:
            audio_path: Path to the input audio file.
            output_dir: Directory to write intermediate files.
            progress_callback: Optional (progress_pct, message) callback.

        Returns:
            Dict mapping stem name to numpy array.
        """
        audio_path = Path(audio_path)
        output_dir = Path(output_dir)

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Keep the config's output_dir in sync with the directory we actually
        # point the separator at. process_chunk() uses config.output_dir for
        # both the temp input file and the separated-stem lookup, so if they
        # diverge (e.g. the API passes a per-job dir while config keeps its
        # default), the stems get written here but looked for elsewhere.
        self.config.output_dir = output_dir

        logger.info(f"Separating audio: {audio_path} with model {self.config.model_key}")

        with _separation_lock:
            if progress_callback:
                progress_callback(0, "Loading separation model")

            separator = self._create_separator(output_dir)

            if progress_callback:
                progress_callback(10, "Loading and resampling audio")

            audio, original_sr = load_audio(audio_path)

            sr = self.config.sample_rate
            if original_sr != sr:
                logger.info(f"Resampling from {original_sr}Hz to {sr}Hz")
                audio = torchaudio.functional.resample(audio, original_sr, sr)

            duration = audio.shape[1] / sr

            if duration <= self.config.chunk_duration:
                return self._separate_whole(
                    audio, sr, separator, duration, progress_callback,
                )

            logger.info(
                f"Chunked processing: {self.config.chunk_duration}s chunks, "
                f"{self.config.overlap}s overlap"
            )
            return self._separate_with_chunking(audio, sr, separator, progress_callback)

    def _separate_whole(
        self,
        audio: torch.Tensor,
        sr: int,
        separator,
        duration: float,
        progress_callback: Optional[Callable[[int, str], None]],
    ) -> dict[str, np.ndarray]:
        logger.info("Processing entire file (no chunking needed)")
        if progress_callback:
            progress_callback(20, "Separating audio into stems")

        stop_estimator = threading.Event()
        if progress_callback:
            estimated_seconds = max(
                duration * self.config.estimated_realtime_factor, 15,
            )
            _start_progress_estimator(
                progress_callback, stop_estimator,
                start_pct=20, end_pct=95,
                estimated_seconds=estimated_seconds,
            )

        try:
            result = process_chunk(audio, sr, separator, self.config)
        finally:
            stop_estimator.set()

        if progress_callback:
            progress_callback(100, "Separation complete")
        return result

    def _separate_with_chunking(
        self,
        audio: torch.Tensor,
        sr: int,
        separator,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> dict[str, np.ndarray]:
        chunk_samples = self.config.chunk_duration * sr
        overlap_samples = self.config.overlap * sr
        step_samples = chunk_samples - overlap_samples

        total_samples = audio.shape[1]
        total_chunks = len(range(0, total_samples, step_samples))
        duration_minutes = total_samples / sr / 60

        chunks = []
        for chunk_num, start in enumerate(range(0, total_samples, step_samples), 1):
            end = min(start + chunk_samples, total_samples)
            chunk = audio[:, start:end]

            logger.info(f"Processing chunk {chunk_num}/{total_chunks}")

            chunk_progress = int(20 + (chunk_num / total_chunks) * 70)
            if progress_callback:
                progress_callback(
                    chunk_progress,
                    f"Separating chunk {chunk_num}/{total_chunks} "
                    f"({duration_minutes:.1f} min audio)",
                )

            if self.config.clear_cache_between_chunks:
                clear_memory(self.device)

            logger.debug(f"Chunk range: {start / sr:.1f}s - {end / sr:.1f}s")
            separated_chunk = process_chunk(chunk, sr, separator, self.config)
            chunks.append(separated_chunk)

        if progress_callback:
            progress_callback(95, "Merging separated chunks")

        clear_memory(self.device)
        result = merge_chunks(chunks, overlap_samples)

        if progress_callback:
            progress_callback(100, "Separation complete")

        return result


def _start_progress_estimator(
    callback: Callable[[int, str], None],
    stop_event: threading.Event,
    start_pct: int,
    end_pct: int,
    estimated_seconds: float,
    interval: float = 2.0,
) -> None:
    """Background thread for smooth progress updates during separation."""
    def _run():
        elapsed = 0.0
        while not stop_event.is_set():
            stop_event.wait(timeout=interval)
            elapsed += interval
            ratio = min(elapsed / estimated_seconds, 1.0)
            pct = int(start_pct + (end_pct - start_pct) * ratio)
            try:
                callback(pct, f"Separating audio ({int(elapsed)}s elapsed)")
            except Exception:
                break

    t = threading.Thread(target=_run, daemon=True)
    t.start()
