from dataclasses import dataclass, field


@dataclass
class PitchFrame:
    time: float
    frequency: float
    confidence: float
    midi_pitch: float = 0.0

    @property
    def is_voiced(self) -> bool:
        return self.frequency > 0 and self.confidence > 0


@dataclass
class NoteEvent:
    start_time: float
    end_time: float
    anchor_midi: int
    pitch_contour: list[PitchFrame] = field(default_factory=list)
    velocity: int = 100

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class TranscriptionResult:
    notes: list[NoteEvent] = field(default_factory=list)
    pitch_contour: list[PitchFrame] = field(default_factory=list)
    tempo_bpm: float = 120.0
    duration: float = 0.0
    sample_rate: int = 44100

