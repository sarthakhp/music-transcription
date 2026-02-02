from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
import os

from .constants import KNOWN_STEMS


@dataclass
class SeparationConfig:
    model_name: str = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"
    model_type: Literal["bs_roformer", "mel_band_roformer", "htdemucs"] = "bs_roformer"

    chunk_duration: int = 60
    overlap: int = 2

    sample_rate: int = 44100
    output_format: Literal["wav", "flac", "mp3"] = "wav"
    output_dir: Path = field(default_factory=lambda: Path("output/separated"))

    device: Literal["mps", "cuda", "cpu", "auto"] = "auto"
    use_float32: bool = True
    seed: int | None = 42

    enable_mps_fallback: bool = True
    clear_cache_between_chunks: bool = True

    stems: list[str] = field(default_factory=lambda: KNOWN_STEMS.copy())

    def __post_init__(self):
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if self.enable_mps_fallback:
            os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

    def get_device(self) -> str:
        if self.device != "auto":
            return self.device
        
        import torch
        if torch.backends.mps.is_available():
            return "mps"
        elif torch.cuda.is_available():
            return "cuda"
        return "cpu"

