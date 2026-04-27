import logging
from pathlib import Path

from .config import InstrumentTranscriptionConfig
from .models import InstrumentNoteEvent, InstrumentTrack
from ._basic_pitch_runner import run_basic_pitch

logger = logging.getLogger(__name__)


class MelodicTranscriber:
    """Transcribe the 'other' stem (guitars, keys, synths) to note events.

    Uses Basic Pitch which handles polyphonic audio — multiple simultaneous
    notes are detected. The output contains all pitched notes without
    instrument labels (guitar vs piano vs synth are not distinguished).
    """

    def __init__(self, config: InstrumentTranscriptionConfig | None = None):
        self.config = config or InstrumentTranscriptionConfig()

    def transcribe(self, audio_path: str | Path) -> InstrumentTrack:
        """Transcribe a polyphonic instrument stem to note events."""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Transcribing melodic stem: {audio_path}")

        note_events = run_basic_pitch(
            audio_path=audio_path,
            onset_threshold=self.config.onset_threshold,
            frame_threshold=self.config.frame_threshold,
            minimum_note_length=self.config.minimum_note_length,
            minimum_frequency=self.config.other_min_frequency,
            maximum_frequency=self.config.other_max_frequency,
            multiple_pitch_bends=self.config.multiple_pitch_bends,
            melodia_trick=self.config.melodia_trick,
        )

        notes = [
            InstrumentNoteEvent(
                onset=event[0],
                offset=event[1],
                pitch=event[2],
                velocity=min(127, max(1, int(event[3] * 127))),
                instrument="other",
                confidence=event[3],
                pitch_bends=list(event[4]) if len(event) > 4 and event[4] is not None else [],
            )
            for event in note_events
        ]

        duration = max((n.offset for n in notes), default=0.0)
        track = InstrumentTrack(instrument="other", notes=notes, duration=duration)

        logger.info(f"Melodic transcription complete: {track.num_notes} notes over {duration:.1f}s")
        return track
