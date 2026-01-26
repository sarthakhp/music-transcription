from dataclasses import dataclass
from typing import Literal

import torch


@dataclass
class TranscriptionConfig:
    # Time between pitch detection frames (lower = more detail, slower processing)
    hop_size_ms: int = 10

    # CREPE model size: tiny/small=fast, full=most accurate for complex vocals
    crepe_model: Literal["tiny", "small", "medium", "large", "full"] = "full"

    # Pitch decoding: viterbi adds temporal smoothing, reduces octave jumps
    decoder: Literal["argmax", "weighted_argmax", "viterbi"] = "viterbi"

    # Frames below this confidence are marked unvoiced (0.0-1.0)
    confidence_threshold: float = 0.3

    # Audio below this level treated as silence
    silence_threshold_db: float = -40.0

    # Notes shorter than this get merged with neighbors
    min_note_duration_ms: int = 40

    # Max pitch variance (semitones) for a region to be considered "stable"
    pitch_stability_threshold: float = 0.5

    # Silence gap longer than this creates a new note
    note_gap_threshold_ms: int = 80

    # Pitch jump larger than this (semitones) creates a note boundary
    pitch_jump_threshold: float = 1.5

    # Median filter window size for removing pitch spikes
    median_filter_size: int = 5

    # Pitch jumps larger than this (semitones) trigger octave correction
    octave_jump_threshold: float = 10.0

    # Processing device: auto detects best available (cuda > mps > cpu)
    device: Literal["auto", "cuda", "mps", "cpu"] = "auto"

    # Number of frames to process at once (higher = faster, more memory)
    batch_size: int = 2048

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

    def get_hop_samples(self, sample_rate: int = 44100) -> int:
        return int(sample_rate * self.hop_size_ms / 1000)

