import logging

import numpy as np
from scipy.ndimage import median_filter

from .config import TranscriptionConfig
from .models import PitchFrame

logger = logging.getLogger(__name__)


class PitchProcessor:
    def __init__(self, config: TranscriptionConfig | None = None):
        self.config = config or TranscriptionConfig()

    def process(self, frames: list[PitchFrame]) -> list[PitchFrame]:
        if not frames:
            return frames

        frames = self._filter_by_confidence(frames)
        frames = self._apply_median_filter(frames)
        frames = self._correct_octave_errors(frames)

        voiced_count = sum(1 for f in frames if f.is_voiced)
        logger.info(f"Processed {len(frames)} frames, {voiced_count} voiced ({100*voiced_count/len(frames):.1f}%)")

        return frames

    def _filter_by_confidence(self, frames: list[PitchFrame]) -> list[PitchFrame]:
        threshold = self.config.confidence_threshold
        result = []

        for frame in frames:
            if frame.confidence < threshold:
                result.append(PitchFrame(
                    time=frame.time,
                    frequency=0.0,
                    confidence=frame.confidence,
                    midi_pitch=0.0,
                ))
            else:
                result.append(frame)

        filtered_count = sum(1 for f in result if f.frequency == 0)
        logger.debug(f"Confidence filter: {filtered_count} frames below threshold {threshold}")
        return result

    def _apply_median_filter(self, frames: list[PitchFrame]) -> list[PitchFrame]:
        if len(frames) < self.config.median_filter_size:
            return frames

        midi_values = np.array([f.midi_pitch for f in frames])
        voiced_mask = midi_values > 0

        if not np.any(voiced_mask):
            return frames

        voiced_midi = midi_values.copy()
        voiced_midi[~voiced_mask] = np.nan

        valid_indices = np.where(voiced_mask)[0]
        if len(valid_indices) >= self.config.median_filter_size:
            valid_values = midi_values[voiced_mask]
            filtered_values = median_filter(valid_values, size=self.config.median_filter_size, mode='nearest')

            for i, idx in enumerate(valid_indices):
                frames[idx].midi_pitch = filtered_values[i]
                frames[idx].frequency = self._midi_to_frequency(filtered_values[i])

        return frames

    def _correct_octave_errors(self, frames: list[PitchFrame]) -> list[PitchFrame]:
        threshold = self.config.octave_jump_threshold
        corrections = 0

        for i in range(1, len(frames) - 1):
            if not frames[i].is_voiced:
                continue

            prev_voiced = None
            next_voiced = None

            for j in range(i - 1, max(0, i - 5) - 1, -1):
                if frames[j].is_voiced:
                    prev_voiced = frames[j]
                    break

            for j in range(i + 1, min(len(frames), i + 5)):
                if frames[j].is_voiced:
                    next_voiced = frames[j]
                    break

            if prev_voiced and next_voiced:
                current = frames[i].midi_pitch
                expected = (prev_voiced.midi_pitch + next_voiced.midi_pitch) / 2

                if abs(current - expected) > threshold:
                    octave_shift = round((expected - current) / 12) * 12
                    if octave_shift != 0:
                        frames[i].midi_pitch = current + octave_shift
                        frames[i].frequency = self._midi_to_frequency(frames[i].midi_pitch)
                        corrections += 1

        if corrections > 0:
            logger.debug(f"Corrected {corrections} octave errors")

        return frames

    def _midi_to_frequency(self, midi: float) -> float:
        if midi <= 0:
            return 0.0
        return 440.0 * (2 ** ((midi - 69) / 12))

