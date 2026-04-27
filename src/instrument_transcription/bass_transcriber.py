import logging
from pathlib import Path

from .config import InstrumentTranscriptionConfig
from .models import InstrumentNoteEvent, InstrumentTrack
from ._basic_pitch_runner import run_basic_pitch

logger = logging.getLogger(__name__)


class BassTranscriber:
    def __init__(self, config: InstrumentTranscriptionConfig | None = None):
        self.config = config or InstrumentTranscriptionConfig()

    def transcribe(self, audio_path: str | Path) -> InstrumentTrack:
        """Transcribe a bass stem to note events using Basic Pitch."""
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Bass audio file not found: {audio_path}")

        logger.info(f"Transcribing bass stem: {audio_path}")

        note_events = run_basic_pitch(
            audio_path=audio_path,
            onset_threshold=self.config.onset_threshold,
            frame_threshold=self.config.frame_threshold,
            minimum_note_length=self.config.minimum_note_length,
            minimum_frequency=self.config.bass_min_frequency,
            maximum_frequency=self.config.bass_max_frequency,
            multiple_pitch_bends=self.config.multiple_pitch_bends,
            melodia_trick=self.config.melodia_trick,
        )

        notes = [
            InstrumentNoteEvent(
                onset=event[0],
                offset=event[1],
                pitch=event[2],
                velocity=min(127, max(1, int(event[3] * 127))),
                instrument="bass",
                confidence=event[3],
                pitch_bends=list(event[4]) if len(event) > 4 and event[4] is not None else [],
            )
            for event in note_events
        ]

        duration = max((n.offset for n in notes), default=0.0)
        track = InstrumentTrack(instrument="bass", notes=notes, duration=duration)

        logger.info(f"Bass transcription complete: {track.num_notes} notes over {duration:.1f}s")
        return track
