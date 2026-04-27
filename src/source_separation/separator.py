import logging
import threading
import time
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


# Module-level state for the singleton.
# The preload step ensures the model *file* is downloaded to disk at startup
# (eliminating the download race). Per-job, a fresh audio_separator.Separator
# is created with the correct output_dir — load_model() is a fast ~2-3s disk
# read since the file is already cached.
_instance: Optional["AppleSiliconSeparator"] = None
_separation_lock = threading.Lock()


class AppleSiliconSeparator:
    def __init__(self, config: SeparationConfig | None = None):
        self.config = config or SeparationConfig()
        self.device = self.config.get_device()

        if self.config.seed is not None:
            torch.manual_seed(self.config.seed)
            if self.device == "mps":
                torch.mps.manual_seed(self.config.seed)

        logger.info(f"Initialized AppleSiliconSeparator with device: {self.device}")

    # ------------------------------------------------------------------
    # Singleton lifecycle
    # ------------------------------------------------------------------

    @classmethod
    def preload(cls, config: SeparationConfig | None = None) -> "AppleSiliconSeparator":
        """Download and verify the model file at startup.

        Creates a temporary Separator to trigger the download, then discards it.
        Per-job Separator instances will load the cached model from disk (fast).
        Subsequent calls are no-ops.
        """
        global _instance
        if _instance is not None:
            logger.info("AppleSiliconSeparator already preloaded, skipping")
            return _instance

        logger.info("Preloading source separation model...")
        instance = cls(config)
        instance._download_model()
        _instance = instance
        logger.info("Source separation model preloaded successfully")
        return _instance

    @classmethod
    def get_instance(cls) -> "AppleSiliconSeparator":
        """Return the preloaded singleton. Raises if preload() was never called."""
        if _instance is None:
            raise RuntimeError(
                "AppleSiliconSeparator has not been preloaded. "
                "Call AppleSiliconSeparator.preload() at startup."
            )
        return _instance

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    def _download_model(self):
        """Ensure the model file is downloaded and loadable."""
        from audio_separator.separator import Separator

        separator = Separator(
            output_dir=str(self.config.output_dir),
            output_format=self.config.output_format,
        )
        separator.load_model(model_filename=self.config.model_name)
        logger.info(f"Model verified: {self.config.model_name}")

    def _create_separator(self, output_dir: Path) -> "Separator":
        """Create a fresh audio_separator.Separator with the correct output_dir.

        The model file is already cached on disk from preload(), so load_model()
        is a fast disk read (~2-3s), not a download.
        """
        from audio_separator.separator import Separator

        separator = Separator(
            output_dir=str(output_dir),
            output_format=self.config.output_format,
        )
        separator.load_model(model_filename=self.config.model_name)
        return separator

    # ------------------------------------------------------------------
    # Separation
    # ------------------------------------------------------------------

    def separate(
        self,
        audio_path: str | Path,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        output_dir: str | Path | None = None,
    ) -> dict[str, np.ndarray]:
        """Separate audio into stems.

        Args:
            audio_path: Path to the input audio file.
            progress_callback: Optional callback receiving (progress_pct, message).
            output_dir: Per-job output directory. Each call creates a fresh
                        audio_separator.Separator with this directory so files
                        are written to the correct location.
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Separating audio: {audio_path}")

        with _separation_lock:
            if output_dir is not None:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                self.config.output_dir = output_dir

            if progress_callback:
                progress_callback(0, "Loading separation model")

            separator = self._create_separator(self.config.output_dir)

            if progress_callback:
                progress_callback(10, "Loading and resampling audio")

            audio, original_sr = load_audio(audio_path)

            sr = 44100
            if original_sr != sr:
                logger.info(f"Resampling input from {original_sr}Hz to {sr}Hz (model's native rate)")
                audio = torchaudio.functional.resample(audio, original_sr, sr)

            duration = audio.shape[1] / sr

            if duration <= self.config.chunk_duration:
                logger.info("Processing entire file (no chunking needed)")
                if progress_callback:
                    progress_callback(20, "Separating audio into stems")

                # audio_separator doesn't expose a progress callback, so run a
                # time-based estimator in a background thread. Separation speed
                # is roughly 1.2-1.5x real-time on MPS.
                stop_estimator = threading.Event()
                if progress_callback:
                    estimated_seconds = max(duration * 1.4, 15)
                    self._start_progress_estimator(
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

            logger.info(f"Processing in {self.config.chunk_duration}s chunks with {self.config.overlap}s overlap")
            return self._separate_with_chunking(audio, sr, separator, progress_callback)

    @staticmethod
    def _start_progress_estimator(
        callback: Callable[[int, str], None],
        stop_event: threading.Event,
        start_pct: int,
        end_pct: int,
        estimated_seconds: float,
        interval: float = 2.0,
    ):
        """Run a background thread that smoothly updates progress while
        the actual separation (which has no progress API) is blocking."""
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

    def _separate_with_chunking(
        self,
        audio: torch.Tensor,
        sr: int,
        separator,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> dict[str, np.ndarray]:
        chunk_samples = self.config.chunk_duration * sr
        overlap_samples = self.config.overlap * sr

        chunks = []
        total_samples = audio.shape[1]
        step_samples = chunk_samples - overlap_samples
        total_chunks = len(range(0, total_samples, step_samples))

        duration_minutes = total_samples / sr / 60

        for chunk_num, start in enumerate(range(0, total_samples, step_samples), 1):
            end = min(start + chunk_samples, total_samples)
            chunk = audio[:, start:end]

            logger.info(f"Processing chunk {chunk_num} of {total_chunks}")

            chunk_progress = int(20 + (chunk_num / total_chunks) * 70)
            if progress_callback:
                progress_callback(
                    chunk_progress,
                    f"Separating chunk {chunk_num}/{total_chunks} ({duration_minutes:.1f} min audio)"
                )

            if self.config.clear_cache_between_chunks:
                clear_memory(self.device)

            logger.debug(f"Processing chunk: {start/sr:.1f}s - {end/sr:.1f}s")
            separated_chunk = process_chunk(chunk, sr, separator, self.config)
            chunks.append(separated_chunk)

        if progress_callback:
            progress_callback(95, "Merging separated chunks")

        clear_memory(self.device)
        result = merge_chunks(chunks, overlap_samples)

        if progress_callback:
            progress_callback(100, "Separation complete")

        return result
