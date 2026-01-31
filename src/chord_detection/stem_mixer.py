import logging
from pathlib import Path

import numpy as np
import soundfile as sf

from .config import ChordDetectionConfig

logger = logging.getLogger(__name__)


class StemMixer:
    def __init__(self, config: ChordDetectionConfig | None = None):
        self.config = config or ChordDetectionConfig()

    def mix_stems(
        self,
        bass_path: str | Path | None = None,
        other_path: str | Path | None = None,
        instrumental_path: str | Path | None = None,
        output_path: str | Path | None = None,
    ) -> tuple[np.ndarray, int]:
        if bass_path is None and other_path is None and instrumental_path is None:
            raise ValueError("At least one stem path must be provided")

        if instrumental_path is not None:
            instrumental_path = Path(instrumental_path)
            logger.info(f"Using instrumental stem directly: {instrumental_path}")
            audio, sr = sf.read(instrumental_path)

            if audio.ndim > 1:
                audio = audio.mean(axis=1)

            if self.config.normalize_mix:
                peak = np.abs(audio).max()
                if peak > 0:
                    target_peak = 10 ** (self.config.peak_normalize_db / 20.0)
                    audio = audio * (target_peak / peak)
                    logger.info(f"Normalized to {self.config.peak_normalize_db}dB (peak={target_peak:.3f})")

            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                sf.write(output_path, audio, sr)
                logger.info(f"Saved audio to: {output_path}")

            logger.info(f"Audio: {len(audio)} samples, {len(audio)/sr:.2f}s, sr={sr}Hz")
            return audio, sr

        stems_to_mix = []
        weights = []
        sample_rates = []

        if bass_path is not None:
            bass_path = Path(bass_path)
            logger.info(f"Loading bass stem: {bass_path}")
            bass, sr_bass = sf.read(bass_path)
            if bass.ndim > 1:
                bass = bass.mean(axis=1)
            stems_to_mix.append(bass)
            weights.append(self.config.bass_weight)
            sample_rates.append(sr_bass)

        if other_path is not None:
            other_path = Path(other_path)
            logger.info(f"Loading other stem: {other_path}")
            other, sr_other = sf.read(other_path)
            if other.ndim > 1:
                other = other.mean(axis=1)
            stems_to_mix.append(other)
            weights.append(self.config.other_weight)
            sample_rates.append(sr_other)

        if len(set(sample_rates)) > 1:
            raise ValueError(f"Sample rate mismatch: {sample_rates}")

        sr = sample_rates[0]

        min_length = min(len(stem) for stem in stems_to_mix)
        stems_to_mix = [stem[:min_length] for stem in stems_to_mix]

        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]

        logger.info(f"Mixing {len(stems_to_mix)} stems with normalized weights: {normalized_weights}")
        mixed = sum(stem * weight for stem, weight in zip(stems_to_mix, normalized_weights))

        if self.config.normalize_mix:
            peak = np.abs(mixed).max()
            if peak > 0:
                target_peak = 10 ** (self.config.peak_normalize_db / 20.0)
                mixed = mixed * (target_peak / peak)
                logger.info(f"Normalized to {self.config.peak_normalize_db}dB (peak={target_peak:.3f})")

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, mixed, sr)
            logger.info(f"Saved mixed audio to: {output_path}")

        logger.info(f"Mixed audio: {len(mixed)} samples, {len(mixed)/sr:.2f}s, sr={sr}Hz")
        return mixed, sr

