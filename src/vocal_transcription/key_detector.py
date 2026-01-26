import logging
from collections import Counter

import numpy as np

from .config import TranscriptionConfig
from .constants import A4_FREQUENCY, A4_MIDI
from .models import PitchFrame, KeyInfo

logger = logging.getLogger(__name__)

CHROMATIC_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SWARA_NAMES = ["Sa", "Re_k", "Re", "Ga_k", "Ga", "Ma", "Ma_t", "Pa", "Dha_k", "Dha", "Ni_k", "Ni"]

COMMON_SCALES = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
    "bilawal": [0, 2, 4, 5, 7, 9, 11],
    "kafi": [0, 2, 3, 5, 7, 9, 10],
    "bhairav": [0, 1, 4, 5, 7, 8, 11],
    "kalyan": [0, 2, 4, 6, 7, 9, 11],
    "khamaj": [0, 2, 4, 5, 7, 9, 10],
    "asavari": [0, 2, 3, 5, 7, 8, 10],
    "bhairavi": [0, 1, 3, 5, 7, 8, 10],
    "marwa": [0, 1, 4, 6, 7, 9, 11],
    "purvi": [0, 1, 4, 6, 7, 8, 11],
    "todi": [0, 1, 3, 6, 7, 8, 11],
}


class KeyScaleDetector:
    def __init__(self, config: TranscriptionConfig | None = None):
        self.config = config or TranscriptionConfig()

    def detect(self, frames: list[PitchFrame]) -> KeyInfo:
        if not frames:
            return self._create_default_key_info()

        voiced_frames = [f for f in frames if f.is_voiced]
        if not voiced_frames:
            return self._create_default_key_info()

        logger.info(f"Detecting key from {len(voiced_frames)} voiced frames")

        pitch_class_histogram = self._build_pitch_class_histogram(voiced_frames)
        
        tonic_midi, tonic_confidence = self._detect_tonic(pitch_class_histogram, voiced_frames)
        
        scale_type, scale_intervals = self._detect_scale(pitch_class_histogram, tonic_midi)
        
        tonic_frequency = self._midi_to_frequency(tonic_midi)
        tonic_name = CHROMATIC_NOTES[tonic_midi % 12]
        
        detected_notes = self._get_detected_notes(pitch_class_histogram)
        swara_usage = self._calculate_swara_usage(pitch_class_histogram, tonic_midi)

        key_info = KeyInfo(
            tonic_midi=tonic_midi,
            tonic_frequency=tonic_frequency,
            tonic_name=tonic_name,
            scale_type=scale_type,
            scale_intervals=scale_intervals,
            swara_usage=swara_usage,
            confidence=tonic_confidence,
            detected_notes=detected_notes,
        )

        logger.info(f"Detected key: {tonic_name} {scale_type} (confidence: {tonic_confidence:.2f})")
        logger.info(f"Scale intervals: {scale_intervals}")
        
        return key_info

    def _build_pitch_class_histogram(self, frames: list[PitchFrame]) -> np.ndarray:
        histogram = np.zeros(12)
        
        for frame in frames:
            pitch_class = int(round(frame.midi_pitch)) % 12
            histogram[pitch_class] += frame.confidence
        
        if histogram.sum() > 0:
            histogram = histogram / histogram.sum()
        
        return histogram

    def _detect_tonic(self, histogram: np.ndarray, frames: list[PitchFrame]) -> tuple[int, float]:
        midi_notes = [int(round(f.midi_pitch)) for f in frames]
        note_counts = Counter(midi_notes)
        
        if not note_counts:
            return 60, 0.0
        
        most_common_midi = note_counts.most_common(1)[0][0]
        
        pitch_class = most_common_midi % 12
        
        octave_candidates = {}
        for midi_note, count in note_counts.items():
            if midi_note % 12 == pitch_class:
                octave_candidates[midi_note] = count
        
        if octave_candidates:
            tonic_midi = max(octave_candidates.items(), key=lambda x: x[1])[0]
        else:
            tonic_midi = most_common_midi
        
        confidence = histogram[pitch_class]
        
        return tonic_midi, float(confidence)

    def _detect_scale(self, histogram: np.ndarray, tonic_midi: int) -> tuple[str, list[int]]:
        tonic_class = tonic_midi % 12
        
        rotated_histogram = np.roll(histogram, -tonic_class)
        
        best_scale = "major"
        best_score = 0.0
        
        for scale_name, intervals in COMMON_SCALES.items():
            score = sum(rotated_histogram[interval] for interval in intervals)
            
            if score > best_score:
                best_score = score
                best_scale = scale_name
        
        scale_intervals = COMMON_SCALES[best_scale]
        
        return best_scale, scale_intervals

    def _get_detected_notes(self, histogram: np.ndarray, threshold: float = 0.05) -> list[int]:
        return [i for i in range(12) if histogram[i] > threshold]

    def _calculate_swara_usage(self, histogram: np.ndarray, tonic_midi: int) -> dict[str, float]:
        tonic_class = tonic_midi % 12
        swara_usage = {}
        
        for i in range(12):
            swara_name = SWARA_NAMES[i]
            actual_pitch_class = (tonic_class + i) % 12
            swara_usage[swara_name] = float(histogram[actual_pitch_class])
        
        return swara_usage

    def _midi_to_frequency(self, midi: float) -> float:
        if midi <= 0:
            return 0.0
        return A4_FREQUENCY * (2 ** ((midi - A4_MIDI) / 12))

    def _create_default_key_info(self) -> KeyInfo:
        return KeyInfo(
            tonic_midi=60,
            tonic_frequency=261.63,
            tonic_name="C",
            scale_type="major",
            scale_intervals=[0, 2, 4, 5, 7, 9, 11],
            swara_usage={},
            confidence=0.0,
            detected_notes=[],
        )

