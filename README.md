# Music Transcription Pipeline

A Python-based pipeline for automatic transcription of Hindi/Bollywood music, designed to handle complex vocal ornamentations (gamakas), microtones (shrutis), and non-Western instrumentation.

## Features

- **Source Separation**: Isolates vocals, drums, bass, and other instruments using state-of-the-art BS-RoFormer model
- **Vocal Transcription**: High-resolution pitch detection with TorchCREPE, preserving Hindi music ornamentations
- **MIDI Generation**: Creates MIDI files with pitch bend encoding to capture subtle pitch variations
- **Key & Scale Detection**: Automatically detects the musical key and scale type
- **Tempo Detection**: Extracts tempo information from the original audio
- **Apple Silicon Optimized**: Leverages MPS (Metal Performance Shaders) for GPU acceleration on Mac

## Pipeline Overview

```
Input Audio → Source Separation → Vocal Transcription → MIDI Output
                    ↓
         ┌─────────┼─────────┐
         ↓         ↓         ↓
      Vocals    Drums    Instruments
         ↓
   TorchCREPE (10ms resolution)
         ↓
   Pitch Processing & Smoothing
         ↓
   Note Segmentation
         ↓
   MIDI + Pitch Bend Encoding
```

## Installation

### Prerequisites

- Python 3.9+
- FFmpeg (for audio processing)

### Install Dependencies

```bash
pip install -r requirements.txt
```

### System Requirements

- **GPU Support**: 
  - Apple Silicon (M1/M2/M3): Uses MPS backend
  - NVIDIA GPUs: Uses CUDA backend
  - CPU fallback available

## Usage

### 1. Source Separation

Separate an audio file into individual stems (vocals, drums, bass, other):

```bash
python run_separation.py <audio_file> [output_dir]
```

**Example:**
```bash
python run_separation.py files/song.mp3 output/separated
```

**Output:**
- `song_vocals.mp3` - Vocals stem (320k bitrate)
- `song_drums.mp3` - Drums stem (320k bitrate)
- `song_bass.mp3` - Bass stem (320k bitrate)
- `song_other.mp3` - Other instruments stem (320k bitrate)
- `song_original.mp3` - Original input audio (copied/converted to MP3)

### 2. Vocal Transcription

Transcribe isolated vocals to MIDI with pitch bend encoding:

```bash
python run_transcription.py <vocal_audio_file> [options]
```

**Options:**
- `--output-dir`: Output directory (default: `output/transcription`)
- `--original-audio`: Path to original audio for tempo detection
- `--export-json`: Export detailed transcription data as JSON
- `--export-csv`: Export pitch contour as CSV for analysis
- `--model`: CREPE model size (`tiny`, `small`, `medium`, `large`, `full`)
- `--hop-size`: Hop size in milliseconds (default: 10ms)
- `--device`: Device to use (`auto`, `mps`, `cuda`, `cpu`)

**Example:**
```bash
python run_transcription.py output/separated/song_vocals.mp3 \
    --original-audio files/song.mp3 \
    --export-json \
    --export-csv
```

**Output:**
- `song_vocals.mid` - MIDI file with pitch bend
- `song_vocals.json` - Detailed transcription data (if `--export-json`)
- `song_vocals_pitch.csv` - Pitch contour data (if `--export-csv`)

### Complete Workflow Example

```bash
# Step 1: Separate audio into stems
python run_separation.py files/bollywood_song.mp3 output/separated

# Step 2: Transcribe vocals to MIDI
python run_transcription.py output/separated/bollywood_song_vocals.mp3 \
    --original-audio files/bollywood_song.mp3 \
    --export-json \
    --export-csv \
    --output-dir output/transcription
```

## Project Structure

```
music-transcription/
├── src/
│   ├── source_separation/     # BS-RoFormer-based audio separation
│   └── vocal_transcription/   # TorchCREPE pitch detection & MIDI generation
├── files/                     # Input audio files
├── output/
│   ├── separated/            # Separated audio stems
│   └── transcription/        # MIDI and transcription outputs
├── run_separation.py         # Source separation script
├── run_transcription.py      # Vocal transcription script
└── requirements.txt          # Python dependencies
```

## Technical Details

### Source Separation
- **Model**: BS-RoFormer (Band-Split RoFormer with Rotary Position Embedding)
- **Performance**: ~12.98 dB SDR on MUSDB18 benchmark
- **Processing**: 30-second chunks with 5-second overlap for memory efficiency

### Vocal Transcription
- **Pitch Detection**: TorchCREPE with 10ms hop size for capturing fast ornamentations
- **Model**: Full-size CREPE model with Viterbi decoder
- **Output**: MIDI notes with pitch wheel data (±8192 range, ±200 cents)
- **Features**: Frequency smoothing, voiced/unvoiced detection, note segmentation

## Architecture Documentation

For detailed technical documentation, see:
- [ARCHITECTURE.md](ARCHITECTURE.md) - Overall pipeline architecture
- [SOURCE_SEPARATION_ARCHITECTURE.md](SOURCE_SEPARATION_ARCHITECTURE.md) - Source separation deep-dive
- [VOCAL_TRANSCRIPTION_ARCHITECTURE.md](VOCAL_TRANSCRIPTION_ARCHITECTURE.md) - Vocal transcription details

## License

This project uses various open-source libraries. Please refer to individual library licenses for details.

