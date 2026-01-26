import logging
from pathlib import Path

import torch
import torchaudio

from .config import TranscriptionConfig

logger = logging.getLogger(__name__)


class AudioTrimmer:
    def __init__(self, config: TranscriptionConfig | None = None):
        self.config = config or TranscriptionConfig()
    
    def load_and_trim(self, audio_path: str | Path) -> tuple[torch.Tensor, int, float]:
        audio_path = Path(audio_path)
        audio, sr = torchaudio.load(str(audio_path))
        
        if self.config.should_crop:
            audio = self._trim_audio(audio, sr)
        
        duration = audio.shape[1] / sr
        return audio, sr, duration
    
    def _trim_audio(self, audio: torch.Tensor, sr: int) -> torch.Tensor:
        start_frame = int(self.config.start_time * sr)
        end_frame = int(self.config.end_time * sr) if self.config.end_time is not None else audio.shape[1]
        
        start_frame = max(0, start_frame)
        end_frame = min(audio.shape[1], end_frame)
        
        if start_frame >= end_frame:
            raise ValueError(f"Invalid crop range: start_time={self.config.start_time}, end_time={self.config.end_time}")
        
        trimmed_audio = audio[:, start_frame:end_frame]
        logger.info(f"Cropped audio from {self.config.start_time}s to {self.config.end_time or 'end'}s")
        
        return trimmed_audio

