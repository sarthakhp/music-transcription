import logging
from collections import Counter

from .config import ChordDetectionConfig
from .models import ChordEvent

logger = logging.getLogger(__name__)


class ChordPostProcessor:
    def __init__(self, config: ChordDetectionConfig | None = None):
        self.config = config or ChordDetectionConfig()

    def process(self, raw_predictions: list[tuple[float, str, float]]) -> list[ChordEvent]:
        if not raw_predictions:
            return []

        logger.info(f"Post-processing {len(raw_predictions)} raw predictions")

        chords = self._convert_to_events(raw_predictions)
        
        if self.config.filter_low_confidence > 0:
            chords = self._filter_by_confidence(chords)
        
        if self.config.smooth_chords:
            chords = self._smooth_chords(chords)
        
        chords = self._merge_consecutive(chords)
        chords = self._filter_short_chords(chords)

        logger.info(f"Post-processing complete: {len(chords)} chord events")
        return chords

    def _convert_to_events(self, predictions: list[tuple[float, str, float]]) -> list[ChordEvent]:
        events = []
        current_chord = None
        start_time = 0.0

        for i, (time, label, confidence) in enumerate(predictions):
            if current_chord is None:
                current_chord = label
                start_time = time
            elif label != current_chord:
                events.append(ChordEvent(
                    start_time=start_time,
                    end_time=time,
                    chord_label=current_chord,
                    confidence=confidence,
                ))
                current_chord = label
                start_time = time

        if current_chord is not None and len(predictions) > 0:
            last_time = predictions[-1][0]
            events.append(ChordEvent(
                start_time=start_time,
                end_time=last_time,
                chord_label=current_chord,
                confidence=predictions[-1][2],
            ))

        return events

    def _filter_by_confidence(self, chords: list[ChordEvent]) -> list[ChordEvent]:
        filtered = [c for c in chords if c.confidence >= self.config.filter_low_confidence]
        logger.info(f"Filtered {len(chords) - len(filtered)} low-confidence chords")
        return filtered

    def _smooth_chords(self, chords: list[ChordEvent]) -> list[ChordEvent]:
        if len(chords) < 3:
            return chords

        smoothed = []
        for i in range(len(chords)):
            if i == 0 or i == len(chords) - 1:
                smoothed.append(chords[i])
                continue

            prev_chord = chords[i - 1]
            curr_chord = chords[i]
            next_chord = chords[i + 1]

            if (curr_chord.duration < 0.2 and 
                prev_chord.chord_label == next_chord.chord_label and 
                curr_chord.chord_label != prev_chord.chord_label):
                logger.debug(f"Smoothing short chord at {curr_chord.start_time:.2f}s: {curr_chord.chord_label} -> {prev_chord.chord_label}")
                continue

            smoothed.append(curr_chord)

        return smoothed

    def _merge_consecutive(self, chords: list[ChordEvent]) -> list[ChordEvent]:
        if not chords:
            return []

        merged = [chords[0]]
        for chord in chords[1:]:
            if chord.chord_label == merged[-1].chord_label:
                merged[-1].end_time = chord.end_time
                merged[-1].confidence = max(merged[-1].confidence, chord.confidence)
            else:
                merged.append(chord)

        logger.info(f"Merged {len(chords) - len(merged)} consecutive chords")
        return merged

    def _filter_short_chords(self, chords: list[ChordEvent]) -> list[ChordEvent]:
        min_duration = self.config.min_chord_duration_ms / 1000.0
        filtered = [c for c in chords if c.duration >= min_duration]
        logger.info(f"Filtered {len(chords) - len(filtered)} chords shorter than {min_duration:.3f}s")
        return filtered

