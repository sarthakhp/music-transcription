from dataclasses import dataclass


@dataclass
class InstrumentTranscriptionConfig:
    # Basic Pitch onset detection threshold (0-1, higher = fewer but more
    # confident notes). Lower values catch softer notes but increase false
    # positives.
    onset_threshold: float = 0.5

    # Basic Pitch frame activation threshold (0-1). Frames above this are
    # considered "active" for a given pitch.
    frame_threshold: float = 0.3

    # Minimum note duration in seconds. Notes shorter than this are discarded.
    minimum_note_length: float = 0.058

    # Bass-specific frequency range (Hz).
    bass_min_frequency: float = 30.0    # low B on 5-string bass
    bass_max_frequency: float = 400.0   # upper practical range

    # "Other" stem frequency range (Hz) — covers guitar, keys, synths.
    other_min_frequency: float = 50.0
    other_max_frequency: float = 4000.0

    # Whether to include pitch bend data in note events.
    multiple_pitch_bends: bool = True

    # Multiple notes can be active simultaneously for polyphonic stems.
    melodia_trick: bool = True
