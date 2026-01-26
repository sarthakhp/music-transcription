import logging
from pathlib import Path

import numpy as np
import torch
import torchaudio
import torchcrepe

from .config import TranscriptionConfig
from .constants import SAMPLE_RATE, A4_FREQUENCY, A4_MIDI
from .models import PitchFrame

logger = logging.getLogger(__name__)


def frequency_to_midi(frequency: float) -> float:
    if frequency <= 0:
        return 0.0
    return A4_MIDI + 12 * np.log2(frequency / A4_FREQUENCY)


class PitchDetector:
    def __init__(self, config: TranscriptionConfig | None = None):
        self.config = config or TranscriptionConfig()
        self.device = self.config.get_device()
        logger.info(f"PitchDetector initialized with device: {self.device}")

    def detect(self, audio_path: str | Path) -> list[PitchFrame]:
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        audio, sr = torchaudio.load(str(audio_path))

        if audio.shape[0] > 1:
            audio = audio.mean(dim=0, keepdim=True)

        if sr != SAMPLE_RATE:
            logger.info(f"Resampling from {sr}Hz to {SAMPLE_RATE}Hz")
            audio = torchaudio.functional.resample(audio, sr, SAMPLE_RATE)

        return self._detect_pitch(audio)

    def detect_from_tensor(self, audio: torch.Tensor, sample_rate: int = SAMPLE_RATE) -> list[PitchFrame]:
        if audio.dim() == 1:
            audio = audio.unsqueeze(0)

        if audio.shape[0] > 1:
            audio = audio.mean(dim=0, keepdim=True)

        if sample_rate != SAMPLE_RATE:
            audio = torchaudio.functional.resample(audio, sample_rate, SAMPLE_RATE)

        return self._detect_pitch(audio)

    def _detect_pitch(self, audio: torch.Tensor) -> list[PitchFrame]:
        hop_samples = self.config.get_hop_samples(SAMPLE_RATE)

        logger.info(f"Running TorchCREPE with model={self.config.crepe_model}, hop={hop_samples} samples")

        audio = audio.to(self.device)

        pitch, periodicity = torchcrepe.predict(
            audio,
            SAMPLE_RATE,
            hop_length=hop_samples,
            fmin=50,
            fmax=2000,
            model=self.config.crepe_model,
            decoder=torchcrepe.decode.viterbi if self.config.decoder == "viterbi" else torchcrepe.decode.argmax,
            batch_size=self.config.batch_size,
            device=self.device,
            return_periodicity=True,
        )

        pitch = pitch.squeeze().cpu().numpy()
        periodicity = periodicity.squeeze().cpu().numpy()

        if pitch.ndim == 0:
            pitch = np.array([pitch.item()])
            periodicity = np.array([periodicity.item()])

        frames = []
        hop_seconds = self.config.hop_size_ms / 1000.0

        for i, (freq, conf) in enumerate(zip(pitch, periodicity)):
            time = i * hop_seconds
            midi_pitch = frequency_to_midi(freq) if freq > 0 else 0.0

            frames.append(PitchFrame(
                time=time,
                frequency=float(freq),
                confidence=float(conf),
                midi_pitch=midi_pitch,
            ))

        logger.info(f"Detected {len(frames)} pitch frames over {frames[-1].time:.2f}s")
        return frames

