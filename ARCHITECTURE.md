# Hindi Music Transcription Pipeline - Architecture

## Overview

A Python pipeline for automatic transcription of Hindi/Bollywood music, handling complex vocal ornamentations (gamakas), microtones (shrutis), and non-Western instrumentation.

## Pipeline Flow

```
Input Audio → Source Separation → Parallel Processing → Output
                    ↓
         ┌─────────┼─────────┐
         ↓         ↓         ↓
      Vocals    Drums    Instruments
         ↓                   ↓
   TorchCREPE           Basic Pitch
   (10ms resolution)    (Polyphonic)
         ↓                   ↓
   Pitch Bend Encoding      ↓
   (Anchor + Deviation)     ↓
         ↓                   ↓
   MIDI + Pitch Wheel ←── MIDI Notes
                    ↓
            Chord Recognition
                 (Madmom)
                    ↓
              Chord Chart
```

## Core Components

| Component | Primary Library | Fallback | Purpose |
|-----------|-----------------|----------|---------|
| Source Separation | BS-RoFormer | HT Demucs ft | Split into vocals/drums/bass/other |
| Vocal Pitch Detection | TorchCREPE (GPU) | CREPE (CPU) | High-resolution pitch contour |
| Instrumental Transcription | Basic Pitch | Omnizart | Polyphonic note detection |
| Chord Recognition | Madmom | librosa templates | Chord progression extraction |

## Architectural Approaches

| Approach | Tech Stack | Trade-off | Use Case |
|----------|------------|-----------|----------|
| Lightweight (DSP) | librosa, pYIN, HPS | Fast, lower accuracy | Prototyping |
| Hybrid DL (Recommended) | BS-RoFormer, TorchCREPE, Basic Pitch | Balanced | Production |
| Heavy Transformer | HT Demucs ft, Full CREPE | Slow, highest accuracy | Research |

## Hindi Music: Challenges & Solutions

| Challenge | Problem | Solution |
|-----------|---------|----------|
| **Gamakas** | Continuous pitch oscillations lost in quantization | Pitch Bend MIDI encoding preserves curves |
| **Shrutis** | 22 microtones vs 12 Western semitones | Frame-by-frame pitch tracking (10ms resolution) |
| **Meend** | Slow curved glides between notes | Anchor note + deviation as Pitch Wheel messages |
| **Tanpura Drone** | Harmonic interference | BS-RoFormer isolates cleanly in "other" stem |
| **Ghungroos/Shakers** | High-frequency bleed into vocals | BS-RoFormer superior vocal isolation |

## Pitch Bend Encoding Strategy

Standard MIDI quantizes to nearest semitone, destroying gamaka nuance. Instead:

1. **Detect** pitch contour frame-by-frame (10ms hop)
2. **Identify** anchor note (dominant stable pitch)
3. **Calculate** deviation from anchor (fractional semitones)
4. **Encode** as MIDI Pitch Wheel messages (±2 semitone range)

```
Frequency → MIDI Float → Round to Anchor Note
                      → Decimal becomes Pitch Bend
```

## Output

| Output | Format | Contains |
|--------|--------|----------|
| Separated Tracks | WAV | Vocals, Drums, Bass, Other |
| Vocal Track | MIDI | Notes + Pitch Wheel (gamakas preserved) |
| Instrumental Track | MIDI | Polyphonic notes |
| Chord Progression | JSON/MIDI | Time-synced chord labels |

## Hardware Requirements

| Approach | GPU | RAM | Notes |
|----------|-----|-----|-------|
| Lightweight | Not required | 4GB | CPU only |
| Hybrid DL | NVIDIA (CUDA) | 8GB | Recommended |
| Heavy Transformer | NVIDIA (CUDA) | 16GB+ | Batch processing |

