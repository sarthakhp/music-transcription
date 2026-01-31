# Chord Detection Module

## Overview

This module detects chords from audio by mixing bass and other (instrumental) stems from source separation, then using the BTC (Bi-directional Transformer for Chord Recognition) model for chord recognition.

## Module Structure

```
src/chord_detection/
├── __init__.py           # Public API exports
├── config.py             # ChordDetectionConfig dataclass
├── constants.py          # Chord vocabularies and defaults
├── models.py             # ChordEvent, ChordProgression data models
├── stem_mixer.py         # Mix bass + other stems
├── btc_model.py          # BTC model wrapper and feature extraction
├── post_processor.py     # Chord smoothing, filtering, merging
├── detector.py           # Main orchestrator class
└── exporter.py           # JSON, LAB, CSV export
```

## Data Models

### ChordEvent
```python
@dataclass
class ChordEvent:
    start_time: float      # seconds
    end_time: float        # seconds
    chord_label: str       # e.g., "C:maj", "D:min7"
    confidence: float      # 0-1
    root: str              # e.g., "C", "D#"
    quality: str           # e.g., "maj", "min", "7"
    bass: str              # bass note (for inversions)
```

### ChordProgression
```python
@dataclass
class ChordProgression:
    chords: list[ChordEvent]
    duration: float
    sample_rate: int
    tempo_bpm: float
    key_info: dict
```

## Configuration

```python
@dataclass
class ChordDetectionConfig:
    # Stem mixing
    bass_weight: float = 0.5
    other_weight: float = 0.5
    normalize_mix: bool = True
    peak_normalize_db: float = -1.0
    
    # BTC model
    model_path: str | None = None
    sample_rate: int = 22050
    hop_length: int = 4410
    
    # Post-processing
    min_chord_duration_ms: int = 100
    smooth_chords: bool = True
    filter_low_confidence: float = 0.3
    
    # Device
    device: Literal["auto", "cuda", "mps", "cpu"] = "auto"
    batch_size: int = 8
    
    # Vocabulary
    use_voca: bool = False  # False=maj/min (25), True=extended (97)
```

## Usage Example

```python
from pathlib import Path
from src.chord_detection import ChordDetector, ChordDetectionConfig

# Create detector
config = ChordDetectionConfig(
    bass_weight=0.5,
    other_weight=0.5,
    device="auto",
)
detector = ChordDetector(config)

# Load BTC model (when available)
# detector.load_model("path/to/btc_model.pth")

# Detect chords from stems
progression = detector.detect_from_stems(
    bass_path="output/separated/song_bass.wav",
    other_path="output/separated/song_other.wav",
    tempo_bpm=120.0,
    key_info={"tonic": "C", "scale": "major"},
)

# Export results
detector.save_json(progression, "output/chords.json")
detector.save_lab(progression, "output/chords.lab")
detector.save_csv(progression, "output/chords.csv")
```

## Output Formats

### JSON
```json
{
  "duration": 120.5,
  "sample_rate": 22050,
  "tempo_bpm": 120.0,
  "key_info": {"tonic": "C", "scale": "major"},
  "num_chords": 45,
  "chords": [
    {
      "start_time": 0.0,
      "end_time": 2.5,
      "duration": 2.5,
      "chord_label": "C:maj",
      "confidence": 0.95,
      "root": "C",
      "quality": "maj",
      "bass": ""
    }
  ]
}
```

### LAB (Audacity/Sonic Visualiser)
```
0.000000	2.500000	C:maj
2.500000	5.000000	F:maj
5.000000	7.500000	G:maj
```

### CSV
```csv
start_time,end_time,duration,chord_label,confidence,root,quality,bass
0.000000,2.500000,2.500000,C:maj,0.9500,C,maj,
2.500000,5.000000,2.500000,F:maj,0.9200,F,maj,
```

## Dependencies

- `torch>=2.3.1` - PyTorch for BTC model
- `librosa>=0.10.0` - CQT feature extraction
- `soundfile>=0.12.0` - Audio I/O
- `numpy>=1.24.0` - Numerical operations

## Next Steps

1. **Download BTC model weights** from https://github.com/jayg996/BTC-ISMIR19
2. **Integrate BTC model** into `btc_model.py`
3. **Test on real audio** with bass + other stems
4. **Tune post-processing** parameters for best results

