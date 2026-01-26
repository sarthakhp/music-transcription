# Vocal Pitch Detection & Transcription - Architecture

## Overview

This module takes isolated vocal tracks (e.g., `mitti-ke-bete-120_sec_vocals.wav`) from source separation and produces MIDI output with pitch bend encoding that preserves Hindi music ornamentations (gamakas, meends, shrutis).

## Pipeline Flow

```
Vocals WAV → Preprocessing → Pitch Detection → Post-Processing → MIDI Generation
                                   ↓
┌──────────────────────────────────┴──────────────────────────────────┐
│                                                                      │
▼                                                                      ▼
┌─────────────────────┐                                    ┌─────────────────────┐
│  Frame-by-Frame     │                                    │  Voiced/Unvoiced    │
│  Pitch Contour      │                                    │  Detection          │
│  (TorchCREPE 10ms)  │                                    │  (Confidence-based) │
└─────────────────────┘                                    └─────────────────────┘
          │                                                          │
          ▼                                                          ▼
┌─────────────────────┐                                    ┌─────────────────────┐
│  Pitch Smoothing    │                                    │  Silence Detection  │
│  (Median Filter)    │                                    │  (RMS Threshold)    │
└─────────────────────┘                                    └─────────────────────┘
          │                                                          │
          └────────────────────────┬─────────────────────────────────┘
                                   ▼
                    ┌─────────────────────────────┐
                    │  Note Segmentation          │
                    │  (Stable Pitch Regions)     │
                    └─────────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │  Anchor Note Detection      │
                    │  (Dominant Pitch per Note)  │
                    └─────────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │  Pitch Bend Calculation     │
                    │  (Deviation from Anchor)    │
                    └─────────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │  MIDI Generation            │
                    │  (Notes + Pitch Wheel)      │
                    └─────────────────────────────┘
```

## Module Structure

```
src/
└── vocal_transcription/
    ├── __init__.py
    ├── config.py              # TranscriptionConfig dataclass
    ├── constants.py           # MIDI constants, frequency ranges
    ├── pitch_detector.py      # TorchCREPE wrapper with GPU/CPU fallback
    ├── pitch_processor.py     # Smoothing, filtering, voiced detection
    ├── note_segmenter.py      # Segment pitch contour into notes
    ├── pitch_bend_encoder.py  # Anchor detection + bend calculation
    ├── midi_generator.py      # MIDI file creation with pitch wheel
    ├── transcriber.py         # Main orchestrator class
    └── utils.py               # Audio loading, time conversion helpers
```

## Core Components

### 1. Pitch Detector (`pitch_detector.py`)

**Purpose**: Extract raw pitch contour from vocals using TorchCREPE

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Hop Size | 10ms (441 samples @ 44.1kHz) | Captures fast gamakas (5-15 oscillations/sec) |
| Model Size | "full" | Best accuracy for complex vocals |
| Decoder | "viterbi" | Temporal smoothing, reduces octave errors |
| Batch Size | 2048 frames | Memory-efficient for long files |

**Output**: 
- `times`: Array of timestamps (seconds)
- `frequencies`: Array of F0 values (Hz), 0 for unvoiced
- `confidence`: Array of voicing confidence [0-1]

### 2. Pitch Processor (`pitch_processor.py`)

**Purpose**: Clean and validate raw pitch data

| Stage | Method | Purpose |
|-------|--------|---------|
| Confidence Filter | threshold=0.6 | Remove low-confidence frames |
| Silence Detection | RMS < -40dB | Mark silent regions |
| Median Filter | window=5 frames | Remove pitch spikes |
| Octave Correction | ±12 semitone jump detection | Fix octave errors |

### 3. Note Segmenter (`note_segmenter.py`)

**Purpose**: Convert continuous pitch contour into discrete note events

**Algorithm**:
1. Identify "stable" regions (pitch variance < 0.5 semitones over 50ms)
2. Detect note boundaries at:
   - Silence gaps > 50ms
   - Pitch jumps > 2 semitones
   - Confidence drops below threshold
3. Merge very short notes (< 80ms) with neighbors
4. Output: List of `NoteEvent(start_time, end_time, pitch_contour)`

### 4. Pitch Bend Encoder (`pitch_bend_encoder.py`)

**Purpose**: Preserve microtonal ornamentations in MIDI format

**Anchor Note Detection**:
```
For each NoteEvent:
    1. Compute pitch histogram (0.1 semitone bins)
    2. Find dominant peak = anchor_pitch
    3. Round anchor to nearest MIDI note
    4. Calculate frame-by-frame deviation from anchor
```

**Pitch Bend Encoding**:
| Parameter | Value | Notes |
|-----------|-------|-------|
| Bend Range | ±2 semitones | Standard MIDI pitch wheel range |
| Resolution | 14-bit (16384 values) | ~0.024 cents per step |
| Update Rate | Every 10ms | Matches pitch detection hop |

### 5. MIDI Generator (`midi_generator.py`)

**Purpose**: Create MIDI file with notes and pitch wheel messages

**Output Structure**:
```
MIDI File
├── Track 0: Metadata (tempo, time signature)
└── Track 1: Vocals
    ├── Note On/Off events (anchor notes)
    └── Pitch Wheel events (continuous ornamentations)
```

## Data Models

```python
@dataclass
class PitchFrame:
    time: float           # seconds
    frequency: float      # Hz (0 = unvoiced)
    confidence: float     # 0-1
    midi_pitch: float     # fractional MIDI note (e.g., 60.45)

@dataclass
class NoteEvent:
    start_time: float     # seconds
    end_time: float       # seconds
    anchor_midi: int      # quantized MIDI note (0-127)
    pitch_contour: list[PitchFrame]  # all frames within note
    velocity: int         # 1-127, derived from RMS

@dataclass
class PitchBendEvent:
    time: float           # seconds
    bend_value: int       # -8192 to +8191 (14-bit)

@dataclass
class TranscriptionResult:
    notes: list[NoteEvent]
    pitch_bends: list[PitchBendEvent]
    tempo_bpm: float
    duration: float
```

## Configuration

```python
@dataclass
class TranscriptionConfig:
    # Pitch Detection
    hop_size_ms: int = 10
    crepe_model: str = "full"        # tiny, small, medium, large, full
    decoder: str = "viterbi"         # argmax, weighted_argmax, viterbi

    # Voicing Detection
    confidence_threshold: float = 0.6
    silence_threshold_db: float = -40.0

    # Note Segmentation
    min_note_duration_ms: int = 80
    pitch_stability_threshold: float = 0.5  # semitones
    note_gap_threshold_ms: int = 50

    # Pitch Bend
    bend_range_semitones: int = 2

    # Device
    device: str = "auto"  # auto, cuda, mps, cpu
```

## Hindi Music Considerations

| Ornament | Characteristics | Detection Strategy |
|----------|-----------------|-------------------|
| **Gamaka** | Rapid oscillation (5-15 Hz) around note | Preserve as pitch bend, don't segment |
| **Meend** | Slow glide between notes (200-500ms) | Single note with continuous bend |
| **Kan Swar** | Grace note, very short (<50ms) | Merge with main note, encode as bend |
| **Murki** | Fast ornamental turn | Preserve full contour in bend data |
| **Andolan** | Slow oscillation on sustained note | Detect via low-frequency pitch variance |

## Algorithm: Gamaka vs Note Boundary Detection

```
For each potential note boundary:
    1. Calculate pitch derivative (semitones/second)
    2. If derivative < 50 st/s AND duration < 100ms:
       → Likely gamaka oscillation, don't segment
    3. If derivative > 100 st/s AND pitch jump > 2 st:
       → Likely note transition, create boundary
    4. If pitch stable (variance < 0.3 st) for > 100ms:
       → Confirm as distinct note
```

## Usage Example

```python
from src.vocal_transcription import VocalTranscriber, TranscriptionConfig

config = TranscriptionConfig(
    hop_size_ms=10,
    confidence_threshold=0.6,
    device="mps"
)

transcriber = VocalTranscriber(config)
result = transcriber.transcribe("output/separated/mitti-ke-bete-120_sec_vocals.wav")

# Save MIDI with pitch bends
transcriber.save_midi(result, "output/mitti-ke-bete-vocals.mid")

# Export pitch contour for visualization
transcriber.export_pitch_csv(result, "output/mitti-ke-bete-pitch.csv")
```

## Output Formats

| Format | Content | Use Case |
|--------|---------|----------|
| `.mid` | Notes + Pitch Wheel | DAW import, playback |
| `.json` | Full transcription data | Analysis, visualization |
| `.csv` | Time, Frequency, MIDI, Confidence | Debugging, plotting |

## Dependencies

```
torchcrepe>=0.0.24      # GPU-accelerated pitch detection
pretty_midi>=0.2.10     # MIDI file creation
mido>=1.3.0             # Low-level MIDI operations
numpy>=1.24.0           # Numerical operations
scipy>=1.10.0           # Signal processing (median filter)
```

## Performance Considerations

| Audio Duration | Processing Time (MPS) | Memory |
|----------------|----------------------|--------|
| 30 seconds | ~3 seconds | ~500MB |
| 2 minutes | ~12 seconds | ~800MB |
| 5 minutes | ~30 seconds | ~1.2GB |

*Benchmarks on Apple M1 Pro with TorchCREPE "full" model*

