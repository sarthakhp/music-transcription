# Chord Detection - Planning Document

## Overview

This document outlines the strategy for adding chord detection capabilities to the music transcription pipeline. The chord detector will analyze mixed instrumental stems (bass + other) to identify chord progressions with timestamps.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Input Source** | Bass + Other stems (mixed) | Cleaner harmonic content, removes vocal interference |
| **Model** | BTC (Bi-directional Transformer) | Highest accuracy, state-of-the-art for chord recognition |
| **Fallback** | None (BTC only) | Acceptable slower speed for offline processing |
| **Integration** | Parallel with vocal transcription | Shares tempo and key information |
| **Output Formats** | JSON, MIDI, CSV, ChordPro | Multiple use cases (analysis, DAW, musicians) |

## Integration Point in Pipeline

```
Input Audio → Source Separation → Parallel Processing → Output
                    ↓
         ┌─────────┼─────────┬─────────┐
         ↓         ↓         ↓         ↓
      Vocals    Drums    Bass      Other
         ↓                   ↓         ↓
   Vocal Transcription      └─────────┘
   (TorchCREPE)                  ↓
         ↓                  Chord Detection
         ↓                  (Chroma + DNN)
         ↓                       ↓
   MIDI + Pitch Wheel      Chord Labels
         └─────────┬─────────────┘
                   ↓
            Combined Output
         (Vocals MIDI + Chords)
```

## Input Sources for Chord Detection

### Selected Approach: Instrumental Stems (Bass + Other)
- **Input**: Combined bass and other stems from source separation
- **Rationale**:
  - Cleaner harmonic content (vocals removed)
  - Better accuracy for vocal-heavy tracks
  - Eliminates vocal melody interference
  - Preserves all instrumental harmonic information
- **Implementation**:
  - Mix bass stem and other stem (equal weighting)
  - Process combined instrumental audio through BTC model

## Technical Approach

### Architecture: BTC (Bi-directional Transformer for Chord Recognition)

#### Overview
BTC is a state-of-the-art deep learning model that uses bi-directional transformers to capture temporal context in both directions, achieving the highest accuracy for chord recognition.

#### Stage 1: Stem Mixing
Combine bass and other stems from source separation.

| Component | Method | Parameters |
|-----------|--------|------------|
| **Input Stems** | Bass + Other from BS-RoFormer | WAV format, 44.1kHz |
| **Mixing Strategy** | Equal amplitude mixing | `mixed = (bass + other) / 2` |
| **Normalization** | Peak normalization to -1dB | Prevent clipping |
| **Output** | Mono instrumental mix | Single channel for chord detection |

#### Stage 2: Feature Extraction
Extract features suitable for BTC model.

| Component | Method | Parameters |
|-----------|--------|------------|
| **Audio Preprocessing** | Resample to model's expected SR | Typically 22.05kHz or 44.1kHz |
| **Frame Size** | Model-dependent | Usually 8192-16384 samples |
| **Hop Size** | Model-dependent | Usually 4096-8192 samples |
| **Feature Type** | CQT or Log-mel Spectrogram | Depends on BTC implementation |

#### Stage 3: BTC Chord Recognition
Apply bi-directional transformer model for chord prediction.

| Component | Description |
|-----------|-------------|
| **Model Type** | Bi-directional Transformer |
| **Context Window** | Captures past and future context |
| **Output** | Chord label per frame with confidence |
| **Vocabulary** | Major, minor, diminished, augmented, 7th, sus4, etc. |
| **Temporal Modeling** | Self-attention mechanism for long-range dependencies |

## Implementation Plan

### Module Structure

```
src/
└── chord_detection/
    ├── __init__.py
    ├── config.py              # ChordDetectionConfig dataclass
    ├── constants.py           # Chord vocabulary, quality mappings
    ├── stem_mixer.py          # Mix bass + other stems
    ├── btc_model.py           # BTC model wrapper and inference
    ├── chord_processor.py     # Post-processing, smoothing, filtering
    ├── chord_exporter.py      # Export to JSON, MIDI, ChordPro
    ├── detector.py            # Main orchestrator class
    └── models.py              # ChordEvent, ChordProgression dataclasses
```

### Data Models

```python
@dataclass
class ChordEvent:
    start_time: float          # seconds
    end_time: float            # seconds
    root: str                  # C, C#, D, etc.
    quality: str               # maj, min, dim, aug, sus4, 7, maj7, etc.
    bass: str | None           # For slash chords (e.g., C/G)
    confidence: float          # 0-1
    label: str                 # Human-readable (e.g., "Cmaj7/G")

@dataclass
class ChordProgression:
    chords: list[ChordEvent]
    duration: float            # total duration in seconds
    tempo_bpm: float           # for alignment with MIDI
    key: str | None            # detected key (e.g., "C major")

@dataclass
class ChordDetectionConfig:
    # Stem Mixing
    bass_weight: float = 0.5           # Weight for bass stem (0.5 = equal mix)
    other_weight: float = 0.5          # Weight for other stem
    normalize_mix: bool = True         # Peak normalize to -1dB

    # BTC Model
    model_path: str | None = None      # Path to BTC model weights
    sample_rate: int = 22050           # BTC model's expected sample rate

    # Post-processing
    min_chord_duration_ms: int = 100   # Merge very short chords
    smooth_chords: bool = True         # Remove rapid changes
    filter_low_confidence: float = 0.3 # Threshold for "N" (no chord)

    # Device
    device: str = "auto"  # auto, cuda, mps, cpu
```

## BTC Model Integration

### BTC Model Research & Selection

Before implementation, research and select the best available BTC model:

#### Step 1: Find BTC Implementation
Search for available implementations:
1. **GitHub Search**: "BTC chord recognition", "bi-directional transformer chord"
2. **Paper Repositories**: Check ISMIR 2019 paper supplementary materials
3. **Research Labs**: UCSD Music + Audio Research, JKU Linz, etc.
4. **Model Hubs**: HuggingFace, Papers with Code

#### Step 2: Evaluate Options

| Criteria | What to Check |
|----------|---------------|
| **Code Availability** | Is source code publicly available? |
| **Pre-trained Weights** | Are model weights downloadable? |
| **PyTorch Compatibility** | Compatible with PyTorch 2.3+? |
| **Documentation** | Clear usage instructions? |
| **License** | Permissive license (MIT, Apache, etc.)? |
| **Maintenance** | Recently updated? Active issues/PRs? |

#### Step 3: BTC Model Options

##### Option 1: Original BTC (ISMIR 2019)
- **Paper**: "A Bi-Directional Transformer for Musical Chord Recognition"
- **Authors**: Hao-Wen Dong et al., UCSD
- **Repository**: Search for author's GitHub (jayg996, salu133445, etc.)
- **Pros**: Original implementation, likely well-tested
- **Cons**: May be older PyTorch version

##### Option 2: Community Implementations
- **mir_eval** compatible models
- Reimplementations with modern PyTorch
- **Pros**: May have better documentation, updated dependencies
- **Cons**: Need to verify accuracy matches paper

##### Option 3: Alternative Transformer Models
- **Harmony Transformer** (if available)
- **BERT-based chord models**
- **Pros**: May have better performance
- **Cons**: Different architecture, need to evaluate

### Installation & Setup

```bash
# Install PyTorch (already in requirements.txt)
# torch>=2.3.1
# torchaudio>=2.3.1

# Clone BTC model repository (example)
git clone https://github.com/jayg996/BTC-ISMIR19.git external/btc_model

# Download pre-trained weights
# (Usually provided by model repository)
wget <model_weights_url> -O models/btc_pretrained.pth
```

### Stem Mixing Implementation

```python
import soundfile as sf
import numpy as np

def mix_stems(bass_path: str, other_path: str, output_path: str) -> str:
    """
    Mix bass and other stems for chord detection.

    Args:
        bass_path: Path to bass stem WAV
        other_path: Path to other stem WAV
        output_path: Path to save mixed audio

    Returns:
        Path to mixed audio file
    """
    # Load stems
    bass, sr_bass = sf.read(bass_path)
    other, sr_other = sf.read(other_path)

    # Ensure same sample rate
    assert sr_bass == sr_other, "Sample rates must match"

    # Convert to mono if stereo
    if bass.ndim > 1:
        bass = bass.mean(axis=1)
    if other.ndim > 1:
        other = other.mean(axis=1)

    # Ensure same length (pad shorter one)
    max_len = max(len(bass), len(other))
    if len(bass) < max_len:
        bass = np.pad(bass, (0, max_len - len(bass)))
    if len(other) < max_len:
        other = np.pad(other, (0, max_len - len(other)))

    # Mix with equal weights
    mixed = (bass * 0.5 + other * 0.5)

    # Peak normalize to -1dB
    peak = np.abs(mixed).max()
    if peak > 0:
        mixed = mixed * (0.891 / peak)  # -1dB = 0.891

    # Save mixed audio
    sf.write(output_path, mixed, sr_bass)

    return output_path
```

### BTC Model API Usage (Conceptual)

```python
from src.chord_detection.btc_model import BTCModel

# Initialize BTC model
model = BTCModel(
    model_path="models/btc_pretrained.pth",
    device="mps"  # or "cuda", "cpu"
)

# Process mixed instrumental audio
chords = model.predict(audio_path)
# Returns: [(time, chord_label, confidence), ...]
```

### Chord Label Format
BTC typically outputs labels in Harte notation:
- `N` - No chord / silence
- `C:maj` - C major
- `C:min` - C minor
- `C:maj7` - C major 7th
- `C:min7` - C minor 7th
- `C:sus4` - C suspended 4th
- `C:dim` - C diminished
- `C:aug` - C augmented
- `C:maj6` - C major 6th
- `C:9` - C dominant 9th
- And more extended chords...

## Post-Processing Pipeline

### 1. Chord Smoothing
- **Problem**: Frame-by-frame detection can produce rapid chord changes
- **Solution**: Median filter over 3-5 frames (~300-500ms window)
- **Algorithm**: 
  ```
  For each chord sequence:
      If chord duration < min_duration:
          Merge with previous/next chord based on confidence
  ```

### 2. Confidence Filtering
- **Problem**: Low-confidence detections are often incorrect
- **Solution**: Replace low-confidence chords with "N" (no chord)
- **Threshold**: 0.3 (configurable)

### 3. Key-Aware Correction
- **Problem**: Out-of-key chords may be detection errors
- **Solution**: Use detected key from vocal transcription to validate chords
- **Algorithm**:
  ```
  If chord not in key AND confidence < 0.5:
      Try nearest in-key chord
  ```

### 4. Transition Validation
- **Problem**: Unlikely chord progressions (e.g., C → F#)
- **Solution**: Use music theory rules to validate transitions
- **Common progressions**: I-IV-V, I-V-vi-IV, ii-V-I

## Output Formats

### JSON Format
```json
{
  "duration": 120.5,
  "tempo_bpm": 128.0,
  "key": "C major",
  "chords": [
    {
      "start_time": 0.0,
      "end_time": 2.5,
      "root": "C",
      "quality": "maj",
      "bass": null,
      "confidence": 0.92,
      "label": "C"
    },
    {
      "start_time": 2.5,
      "end_time": 5.0,
      "root": "A",
      "quality": "min",
      "bass": null,
      "confidence": 0.87,
      "label": "Am"
    }
  ]
}
```

### MIDI Format (Chord Track)
```
MIDI File
├── Track 0: Metadata (tempo, time signature)
├── Track 1: Vocals (from vocal transcription)
└── Track 2: Chords (chord markers as text events)
    └── Text Meta Events: "C", "Am", "F", "G" at timestamps
```

### ChordPro Format (for musicians)
```
{title: Mitti Ke Bete}
{key: C}
{tempo: 128}

[C]Verse 1 lyrics here
[Am]More lyrics
[F]Continue [G]lyrics
```

### CSV Format (for analysis)
```csv
start_time,end_time,chord,root,quality,bass,confidence
0.0,2.5,C,C,maj,,0.92
2.5,5.0,Am,A,min,,0.87
5.0,7.5,F,F,maj,,0.89
```

## Integration with Existing Pipeline

### Modified `run_full_pipeline.py` Flow

```python
def main():
    # Step 1: Source Separation (existing)
    stem_paths = run_separation(audio_path, separation_output_dir)

    # Step 2: Vocal Transcription (existing)
    vocal_result = run_transcription(
        stem_paths["vocals"],
        audio_path,
        transcription_output_dir
    )

    # Step 3: Chord Detection (NEW)
    chord_result = run_chord_detection(
        bass_stem_path=stem_paths["bass"],
        other_stem_path=stem_paths["other"],
        output_dir=transcription_output_dir,
        tempo_bpm=vocal_result.tempo_bpm,  # Align with vocals
        key_info=vocal_result.key_info      # Use detected key
    )

    # Step 4: Export Combined Output (NEW)
    export_combined_midi(
        vocal_result=vocal_result,
        chord_result=chord_result,
        output_path=transcription_output_dir / "combined.mid"
    )
```

### New Function: `run_chord_detection()`

```python
def run_chord_detection(
    bass_stem_path: Path,
    other_stem_path: Path,
    output_dir: Path,
    tempo_bpm: float | None = None,
    key_info: KeyInfo | None = None
) -> ChordProgression:
    """
    Detect chords from mixed instrumental stems (bass + other).

    Args:
        bass_stem_path: Path to bass stem WAV file
        other_stem_path: Path to other stem WAV file
        output_dir: Directory to save chord outputs
        tempo_bpm: Optional tempo for alignment (from vocal transcription)
        key_info: Optional key information for validation

    Returns:
        ChordProgression object with detected chords
    """
    from src.chord_detection import ChordDetector, ChordDetectionConfig

    config = ChordDetectionConfig(
        bass_weight=0.5,
        other_weight=0.5,
        normalize_mix=True,
        min_chord_duration_ms=100,
        device="mps"
    )

    detector = ChordDetector(config)
    result = detector.detect(
        bass_stem_path=bass_stem_path,
        other_stem_path=other_stem_path,
        tempo_bpm=tempo_bpm,
        key_info=key_info
    )

    # Export in multiple formats
    base_name = bass_stem_path.stem.replace("_bass", "")
    detector.save_json(result, output_dir / f"{base_name}_chords.json")
    detector.save_csv(result, output_dir / f"{base_name}_chords.csv")
    detector.save_chordpro(result, output_dir / f"{base_name}_chords.cho")

    return result
```

## Performance Considerations

### Processing Time Estimates

| Audio Duration | BTC (CPU) | BTC (GPU/MPS) | Notes |
|----------------|-----------|---------------|-------|
| 30 seconds | ~15-20 seconds | ~5-8 seconds | Transformer inference is slower |
| 2 minutes | ~60-80 seconds | ~20-30 seconds | Acceptable for offline processing |
| 5 minutes | ~150-200 seconds | ~50-75 seconds | ~1-2.5 minutes processing time |

*Estimates based on typical hardware (M1 Pro / NVIDIA RTX 3060). Actual times depend on BTC implementation.*

### Memory Requirements

- **BTC Model**: ~800MB-1.5GB for model weights
- **Audio Processing**: ~150MB per minute of audio (two stems)
- **Peak usage**: ~2-3GB for 5-minute song with BTC
- **Recommendation**: 8GB+ RAM, GPU/MPS strongly recommended

## Dependencies

### Required Packages

```python
# Add to requirements.txt
torch>=2.3.1             # Already included (BTC model backend)
torchaudio>=2.3.1        # Already included (audio processing)
numpy>=1.24.0            # Already included (array operations)
scipy>=1.10.0            # Already included (signal processing)
soundfile>=0.12.0        # Already included (audio I/O)
```

### BTC Model Dependencies

```python
# May be required depending on BTC implementation
transformers>=4.30.0     # If using HuggingFace transformers
einops>=0.6.0            # For tensor operations in transformers
```

### Optional Packages

```python
# For advanced features
mir_eval>=0.7            # Chord evaluation metrics (for testing)
pychord>=0.6.0           # Chord manipulation utilities
```

## Testing Strategy

### Unit Tests

1. **Stem Mixing**: Verify bass+other mixing produces correct output
2. **BTC Model Loading**: Test model initialization and weight loading
3. **Chord Recognition**: Test on known chord progressions
4. **Post-processing**: Validate smoothing and filtering logic
5. **Export Formats**: Ensure valid JSON/MIDI/CSV output

### Integration Tests

1. **Full Pipeline**: Run on sample Hindi songs with bass+other stems
2. **Stem Quality**: Verify mixed instrumental audio is clean
3. **Tempo Alignment**: Verify chord timestamps match vocal MIDI
4. **Key Consistency**: Check chords align with detected key from vocals

### Validation Approach

Since ground truth chord labels are hard to obtain:
1. **Manual Verification**: Listen and verify on 3-5 test songs
2. **Consistency Check**: Same song should produce same chords
3. **Music Theory Validation**: Check for unlikely progressions

## Implementation Phases

### Phase 1: Core Functionality (MVP)
- [ ] Research and select BTC model implementation
- [ ] Download/setup BTC pre-trained model weights
- [ ] Create `chord_detection` module structure
- [ ] Implement stem mixer (bass + other)
- [ ] Implement BTC model wrapper and inference
- [ ] Add JSON export
- [ ] Test BTC on simple chord progressions

**Estimated Time**: 2-3 days

### Phase 2: Pipeline Integration
- [ ] Integrate into `run_full_pipeline.py`
- [ ] Add chord post-processing (smoothing, filtering)
- [ ] Add CSV and MIDI export
- [ ] Test on 2-3 Hindi songs

**Estimated Time**: 2-3 days

### Phase 3: Enhanced Features
- [ ] Add confidence-based filtering
- [ ] Optimize BTC inference for MPS/CUDA
- [ ] Handle edge cases (silence, noise)

**Estimated Time**: 1-2 days

## Success Criteria

### Minimum Viable Product (MVP)
- ✓ Successfully mixes bass + other stems
- ✓ BTC model loads and runs inference
- ✓ Detects major and minor chords with >75% accuracy (BTC baseline)
- ✓ Exports chord progression as JSON
- ✓ Integrates into existing pipeline without breaking

### Production Ready
- ✓ Detects extended chords (7th, sus4, dim, aug) with >70% accuracy
- ✓ Exports to JSON, MIDI, CSV
- ✓ Chord timestamps align with vocal MIDI (±100ms)
- ✓ Processes 5-minute song in <2.5 minutes (acceptable for offline)

## Future Scope

The following features are deferred for future implementation:

### Advanced Features
- **Chord Inversion Detection**: Detect root position vs inversions (e.g., C/E, C/G)
- **Extended Chord Quality Refinement**: Improve detection of complex chords (9th, 11th, 13th)
- **ChordPro Export Format**: Export chords in ChordPro format for musicians
- **Chord Timeline Visualization**: Create visual representation of chord progressions

### Key-Aware Validation
- **Key-Aware Chord Validation**: Use detected key from vocal transcription to validate and correct chord predictions
- **Harmonic Context Analysis**: Leverage key information to improve chord recognition accuracy

### Batch Processing
- **Batch Processing Optimization**: Optimize for processing multiple songs efficiently

## References

### Research Papers
1. **BTC Model**: "A Bi-Directional Transformer for Musical Chord Recognition" (ISMIR 2019)
   - Paper: https://archives.ismir.net/ismir2019/paper/000075.pdf
   - Authors: Hao-Wen Dong, Chris Donahue, Taylor Berg-Kirkpatrick, Julian McAuley
2. **Deep Chroma Features**: Korzeniowski & Widmer (2016) - "Feature Learning for Chord Recognition"
3. **Chord Recognition Survey**: McVicar et al. (2014) - "Automatic Chord Estimation from Audio: A Review of the State of the Art"

### BTC Model Implementations
- **Original BTC (ISMIR 2019)**: https://github.com/jayg996/BTC-ISMIR19 (check for availability)
- **Alternative implementations**: Search GitHub for "BTC chord recognition" or "transformer chord recognition"
- **Pre-trained models**: Check model repositories (HuggingFace, Zenodo, etc.)

### Libraries & Tools
- **PyTorch**: https://pytorch.org/ (already in use)
- **Chord Datasets**: https://github.com/tmc323/Chord-Annotations (for validation)
- **mir_eval**: https://github.com/craffel/mir_eval (chord evaluation metrics)

## Next Steps

1. **Review this document** and confirm approach
2. **Research BTC implementations**:
   - Find available BTC model code (GitHub, research repos)
   - Identify pre-trained weights
   - Check compatibility with PyTorch 2.3+
3. **Setup BTC model**:
   - Clone/download BTC implementation
   - Download pre-trained weights
   - Test inference on sample audio
4. **Create module skeleton** (`src/chord_detection/`)
5. **Implement Phase 1** (MVP):
   - Stem mixer
   - BTC wrapper
   - Basic export
6. **Test on music samples**
7. **Iterate based on results**

