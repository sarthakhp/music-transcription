import logging

import numpy as np

from .config import TranscriptionConfig
from .constants import DEFAULT_VELOCITY
from .models import PitchFrame, NoteEvent

logger = logging.getLogger(__name__)


class NoteSegmenter:
    def __init__(self, config: TranscriptionConfig | None = None):
        self.config = config or TranscriptionConfig()

    def segment(self, frames: list[PitchFrame]) -> list[NoteEvent]:
        if not frames:
            return []

        segments = self._find_voiced_segments(frames)
        notes = self._create_notes_from_segments(segments)
        notes = self._merge_short_notes(notes)
        notes = self._split_on_pitch_jumps(notes)

        logger.info(f"Segmented into {len(notes)} notes")
        return notes

    def _find_voiced_segments(self, frames: list[PitchFrame]) -> list[list[PitchFrame]]:
        segments = []
        current_segment = []
        gap_threshold_sec = self.config.note_gap_threshold_ms / 1000.0
        hop_sec = self.config.hop_size_ms / 1000.0

        for frame in frames:
            if frame.is_voiced:
                if current_segment:
                    gap = frame.time - current_segment[-1].time
                    if gap > gap_threshold_sec + hop_sec:
                        segments.append(current_segment)
                        current_segment = []
                current_segment.append(frame)
            else:
                if current_segment:
                    segments.append(current_segment)
                    current_segment = []

        if current_segment:
            segments.append(current_segment)

        return segments

    def _create_notes_from_segments(self, segments: list[list[PitchFrame]]) -> list[NoteEvent]:
        notes = []

        for segment in segments:
            if not segment:
                continue

            midi_values = [f.midi_pitch for f in segment]
            anchor_midi = self._find_anchor_note(midi_values)

            note = NoteEvent(
                start_time=segment[0].time,
                end_time=segment[-1].time + (self.config.hop_size_ms / 1000.0),
                anchor_midi=anchor_midi,
                pitch_contour=segment.copy(),
                velocity=DEFAULT_VELOCITY,
            )
            notes.append(note)

        return notes

    def _find_anchor_note(self, midi_values: list[float]) -> int:
        if not midi_values:
            return 60

        hist, bin_edges = np.histogram(midi_values, bins=np.arange(30, 90, 0.5))
        peak_idx = np.argmax(hist)
        anchor_pitch = (bin_edges[peak_idx] + bin_edges[peak_idx + 1]) / 2

        return int(round(anchor_pitch))

    def _merge_short_notes(self, notes: list[NoteEvent]) -> list[NoteEvent]:
        if len(notes) < 2:
            return notes

        min_duration_sec = self.config.min_note_duration_ms / 1000.0
        merged = []
        i = 0

        while i < len(notes):
            current = notes[i]

            if current.duration < min_duration_sec and merged:
                prev = merged[-1]
                gap = current.start_time - prev.end_time

                if gap < self.config.note_gap_threshold_ms / 1000.0:
                    prev.end_time = current.end_time
                    prev.pitch_contour.extend(current.pitch_contour)
                    i += 1
                    continue

            merged.append(current)
            i += 1

        return merged

    def _split_on_pitch_jumps(self, notes: list[NoteEvent]) -> list[NoteEvent]:
        result = []

        for note in notes:
            sub_notes = self._split_note_on_jumps(note)
            result.extend(sub_notes)

        return result

    def _split_note_on_jumps(self, note: NoteEvent) -> list[NoteEvent]:
        if len(note.pitch_contour) < 3:
            return [note]

        threshold = self.config.pitch_jump_threshold
        split_indices = [0]

        for i in range(1, len(note.pitch_contour)):
            prev_midi = note.pitch_contour[i - 1].midi_pitch
            curr_midi = note.pitch_contour[i].midi_pitch

            if abs(curr_midi - prev_midi) > threshold:
                split_indices.append(i)

        if len(split_indices) == 1:
            return [note]

        split_indices.append(len(note.pitch_contour))
        sub_notes = []

        for i in range(len(split_indices) - 1):
            start_idx = split_indices[i]
            end_idx = split_indices[i + 1]
            segment = note.pitch_contour[start_idx:end_idx]

            if not segment:
                continue

            midi_values = [f.midi_pitch for f in segment]
            anchor = self._find_anchor_note(midi_values)

            sub_note = NoteEvent(
                start_time=segment[0].time,
                end_time=segment[-1].time + (self.config.hop_size_ms / 1000.0),
                anchor_midi=anchor,
                pitch_contour=segment,
                velocity=note.velocity,
            )
            sub_notes.append(sub_note)

        return sub_notes if sub_notes else [note]

