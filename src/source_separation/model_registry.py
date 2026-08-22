"""Registry of available source separation models.

This is the single source of truth for what models exist, what stems they
produce, and what filenames to pass to audio_separator.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SeparationModel:
    key: str
    display_name: str
    model_filename: str
    stems: list[str] = field(default_factory=list)
    description: str = ""
    estimated_realtime_factor: float = 1.4


MODEL_REGISTRY: dict[str, SeparationModel] = {}

DEFAULT_MODEL_KEY = "bs_roformer_2stem"


def _register(model: SeparationModel) -> None:
    MODEL_REGISTRY[model.key] = model


_register(SeparationModel(
    key="bs_roformer_2stem",
    display_name="BS-RoFormer (2-stem)",
    model_filename="model_bs_roformer_ep_317_sdr_12.9755.ckpt",
    stems=["vocals", "instrumental"],
    description="Fast 2-stem separation: vocals + instrumental. Best for vocal isolation.",
    estimated_realtime_factor=4.0,
))

_register(SeparationModel(
    key="mel_roformer_vocals",
    display_name="Mel-RoFormer (vocals)",
    model_filename="mel_band_roformer_vocals.ckpt",
    stems=["vocals", "instrumental"],
    description="Highest quality vocal isolation using mel-band subbands.",
    estimated_realtime_factor=1.6,
))

_register(SeparationModel(
    key="htdemucs_4stem",
    display_name="HTDemucs (4-stem)",
    model_filename="htdemucs_ft.yaml",
    stems=["vocals", "drums", "bass", "other"],
    description="Meta's Hybrid Transformer Demucs. 4-stem split: vocals, drums, bass, other.",
    estimated_realtime_factor=2.0,
))

_register(SeparationModel(
    key="htdemucs_6stem",
    display_name="HTDemucs (6-stem)",
    model_filename="htdemucs_6s.yaml",
    stems=["vocals", "drums", "bass", "guitar", "piano", "other"],
    description="6-stem variant adding guitar and piano separation.",
    estimated_realtime_factor=2.5,
))

_register(SeparationModel(
    key="bs_roformer_6stem",
    display_name="BS-RoFormer SW (6-stem)",
    model_filename="model_bs_roformer_ep_937_sdr_10.5309.ckpt",
    stems=["vocals", "drums", "bass", "guitar", "piano", "other"],
    description="BS-RoFormer SW for 6-stem separation. Highest quality multi-stem model.",
    estimated_realtime_factor=2.0,
))


def get_model(key: str) -> SeparationModel:
    """Look up a model by key. Raises KeyError with a helpful message."""
    if key not in MODEL_REGISTRY:
        available = ", ".join(sorted(MODEL_REGISTRY))
        raise KeyError(f"Unknown separation model {key!r}. Available: {available}")
    return MODEL_REGISTRY[key]


def list_models() -> list[SeparationModel]:
    return list(MODEL_REGISTRY.values())
