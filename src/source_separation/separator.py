import logging
from pathlib import Path

import torch
import torchaudio
import numpy as np

from .config import SeparationConfig
from .memory import clear_memory
from .chunk_merger import merge_chunks
from .audio_processing import process_chunk

logger = logging.getLogger(__name__)


class AppleSiliconSeparator:
    def __init__(self, config: SeparationConfig | None = None):
        self.config = config or SeparationConfig()
        self.device = self.config.get_device()
        self._separator = None
        self._model_loaded = False

        if self.config.seed is not None:
            torch.manual_seed(self.config.seed)
            if self.device == "mps":
                torch.mps.manual_seed(self.config.seed)

        logger.info(f"Initialized AppleSiliconSeparator with device: {self.device}")

    def _load_model(self):
        if self._model_loaded:
            return

        from audio_separator.separator import Separator

        self._separator = Separator(
            output_dir=str(self.config.output_dir),
            output_format=self.config.output_format,
        )
        self._separator.load_model(model_filename=self.config.model_name)
        self._model_loaded = True
        logger.info(f"Loaded model: {self.config.model_name}")

    def separate(self, audio_path: str | Path) -> dict[str, np.ndarray]:
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Separating audio: {audio_path}")
        self._load_model()

        audio, original_sr = torchaudio.load(str(audio_path))

        sr = 44100
        if original_sr != sr:
            logger.info(f"Resampling input from {original_sr}Hz to {sr}Hz (model's native rate)")
            audio = torchaudio.functional.resample(audio, original_sr, sr)

        duration = audio.shape[1] / sr

        if duration <= self.config.chunk_duration:
            logger.info("Processing entire file (no chunking needed)")
            return process_chunk(audio, sr, self._separator, self.config)

        logger.info(f"Processing in {self.config.chunk_duration}s chunks with {self.config.overlap}s overlap")
        return self._separate_with_chunking(audio, sr)

    def _separate_with_chunking(self, audio: torch.Tensor, sr: int) -> dict[str, np.ndarray]:
        chunk_samples = self.config.chunk_duration * sr
        overlap_samples = self.config.overlap * sr

        chunks = []
        total_samples = audio.shape[1]
        step_samples = chunk_samples - overlap_samples
        total_chunks = len(range(0, total_samples, step_samples))

        for chunk_num, start in enumerate(range(0, total_samples, step_samples), 1):
            end = min(start + chunk_samples, total_samples)
            chunk = audio[:, start:end]

            logger.info(f"Processing chunk {chunk_num} of {total_chunks}")

            if self.config.clear_cache_between_chunks:
                clear_memory(self.device)

            logger.debug(f"Processing chunk: {start/sr:.1f}s - {end/sr:.1f}s")
            separated_chunk = process_chunk(chunk, sr, self._separator, self.config)
            chunks.append(separated_chunk)

        clear_memory(self.device)
        return merge_chunks(chunks, overlap_samples)

