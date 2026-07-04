from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
import os

from .model_registry import DEFAULT_MODEL_KEY, get_model


@dataclass
class SeparationConfig:
    model_key: str = DEFAULT_MODEL_KEY

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

    def __post_init__(self):
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if self.enable_mps_fallback:
            os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

        self._model = get_model(self.model_key)

    @property
    def model_filename(self) -> str:
        return self._model.model_filename

    @property
    def stems(self) -> list[str]:
        return self._model.stems

    @property
    def estimated_realtime_factor(self) -> float:
        return self._model.estimated_realtime_factor

    def get_device(self) -> str:
        if self.device != "auto":
            return self.device

        import torch
        if torch.backends.mps.is_available():
            return "mps"
        elif torch.cuda.is_available():
            return "cuda"
        return "cpu"

