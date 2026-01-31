from dataclasses import dataclass
from typing import Literal

import torch


@dataclass
class ChordDetectionConfig:
    bass_weight: float = 0.5
    other_weight: float = 0.5
    normalize_mix: bool = True
    peak_normalize_db: float = -1.0
    
    model_path: str | None = None
    sample_rate: int = 22050
    hop_length: int = 4410
    
    min_chord_duration_ms: int = 100
    smooth_chords: bool = True
    filter_low_confidence: float = 0.3
    
    device: Literal["auto", "cuda", "mps", "cpu"] = "auto"
    batch_size: int = 8
    
    use_voca: bool = False

    def get_device(self) -> str:
        if self.device != "auto":
            return self.device

        if torch.cuda.is_available():
            print("CUDA is available")
            return "cuda"
        elif torch.backends.mps.is_available():
            print("MPS is available")
            return "mps"

        print("CUDA and MPS are not available, using CPU")
        return "cpu"

