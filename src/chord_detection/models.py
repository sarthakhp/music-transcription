from dataclasses import dataclass, field


@dataclass
class ChordEvent:
    start_time: float
    end_time: float
    chord_label: str
    confidence: float = 0.0
    root: str = ""
    quality: str = ""
    bass: str = ""

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class ChordProgression:
    chords: list[ChordEvent] = field(default_factory=list)
    duration: float = 0.0
    sample_rate: int = 22050
    tempo_bpm: float = 120.0
    key_info: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.chords)

