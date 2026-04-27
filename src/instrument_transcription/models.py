from dataclasses import dataclass, field


@dataclass
class InstrumentNoteEvent:
    """A single detected note from an instrument stem."""
    onset: float           # seconds
    offset: float          # seconds
    pitch: int             # MIDI note number (0-127)
    velocity: int          # 0-127
    instrument: str        # "bass", "drums", "other"
    confidence: float = 0.0
    pitch_bends: list[float] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.offset - self.onset


@dataclass
class InstrumentTrack:
    """All note events for a single instrument stem."""
    instrument: str
    notes: list[InstrumentNoteEvent] = field(default_factory=list)
    duration: float = 0.0

    @property
    def num_notes(self) -> int:
        return len(self.notes)


@dataclass
class InstrumentTranscriptionResult:
    """Combined results from all instrument transcriptions."""
    tracks: dict[str, InstrumentTrack] = field(default_factory=dict)
    duration: float = 0.0

    @property
    def total_notes(self) -> int:
        return sum(track.num_notes for track in self.tracks.values())
