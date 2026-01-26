# Source Separation Architecture for Hindi Music Transcription

## Executive Summary

This document provides a deep-dive into the source separation component of our Hindi music transcription pipeline. Source separation is the critical first stage that isolates vocals, drums, bass, and other instruments before downstream transcription.

---

## State-of-the-Art Models (2025-2026)

### Tier 1: Production-Ready Models

| Model | Architecture | Release | Vocal SDR | Strengths | Weaknesses |
|-------|--------------|---------|-----------|-----------|------------|
| **BS-RoFormer** | Band-Split RoPE Transformer | 2024+ (active 2025) | ~10.5 dB | Best vocal isolation, active development | GPU-heavy, slower inference |
| **MelBand RoFormer** | Mel-band variant of BS-RoFormer | 2024-2025 | ~10.3 dB | 97% ensemble selection rate for vocals | Similar compute requirements |
| **HT Demucs v4** | Hybrid Transformer + U-Net | 2022 (archived Jan 2025) | ~9.0 dB | 4-stem separation, well-tested | No further updates, archived repo |
| **SCNet** | Sparse Compression Network | ICASSP 2024 | ~8.5 dB | Efficient, good baseline | Outperformed by newer models |

### Tier 2: Cutting-Edge Research (2025-2026)

| Model | Architecture | Release | Key Innovation | Status |
|-------|--------------|---------|----------------|--------|
| **SAM Audio** | Multimodal Transformer | Dec 2025 | Text/visual/span prompts for separation | Open-sourced by Meta |
| **BSMamba2** | State Space Model (Mamba2) | Aug 2025 | Handles sparse vocals better than Transformers | Research, code available |
| **Band-SCNet** | Causal SCNet | Interspeech 2025 | Real-time, lightweight, low-latency | Best Student Paper winner |
| **Query-SCNet** | Conditioned SCNet | Dec 2025 | Query-driven source separation | Research |

---

## Model Deep-Dives

### 1. BS-RoFormer (Recommended Primary)

**Architecture Overview:**
- Band-Split: Divides spectrogram into frequency bands
- RoPE (Rotary Position Embedding): Better long-range dependencies
- Transformer backbone: Self-attention across time and frequency

**2025 Updates:**
- Hyper-connections from DeepSeek integrated (Jan 2026)
- MelBand variant uses mel-scale frequency bands
- Active development at `lucidrains/BS-RoFormer`

**Why Best for Hindi Music:**
- Superior vocal isolation preserves subtle gamaka oscillations
- High SDR means less artifact bleed from tanpura drone
- Handles harmonically complex Bollywood arrangements

```
Input Audio (44.1kHz stereo)
    │
    ▼
┌─────────────────────────────────────┐
│  STFT (4096 window, 1024 hop)       │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  Band-Split (61 frequency bands)    │
│  - Low: 0-1kHz (8 bands)            │
│  - Mid: 1-8kHz (32 bands)           │
│  - High: 8-22kHz (21 bands)         │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  Transformer Blocks (12 layers)     │
│  - RoPE positional encoding         │
│  - Multi-head self-attention        │
│  - Feed-forward networks            │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  Band-Merge + Mask Estimation       │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│  iSTFT → Separated Stems            │
│  (vocals, drums, bass, other)       │
└─────────────────────────────────────┘
```

### 2. SAM Audio (Meta, Dec 2025)

**Revolutionary Capabilities:**
- First unified model accepting text, visual, or audio span prompts
- "Separate the female vocalist" → isolates specific singer
- "Remove the tabla" → targets specific Hindi percussion
- Open-sourced by Meta AI

**Prompt Types:**
1. **Text**: "Extract the sitar melody"
2. **Visual**: Image of instrument → isolates that sound
3. **Span**: Audio clip reference → finds similar sources

**Limitations for Our Use Case:**
- Newer, less battle-tested than BS-RoFormer
- May require prompt engineering for Hindi-specific instruments
- Compute-heavy multimodal encoder

### 3. BSMamba2 (Aug 2025)

**Key Innovation:**
State Space Models (SSMs) instead of Transformers for:
- Better handling of sparse vocal tracks
- More efficient long-context modeling
- Reduced artifacts in quiet passages

**When to Use:**
- Songs with extended instrumental sections
- Sparse vocal arrangements common in classical-influenced Bollywood
- Memory-constrained environments

### 4. Band-SCNet (Interspeech 2025 Best Student Paper)

**Real-Time Optimized:**
- Causal architecture (no future frame lookahead)
- Lightweight: suitable for edge deployment
- Low-latency: <50ms processing delay

**Trade-offs:**
- Slight SDR drop vs non-causal models
- Best for live/streaming applications
- Not recommended when quality is paramount

---

## Benchmark Comparison (MUSDB18-HQ, 2025)

| Model | Vocals SDR | Drums SDR | Bass SDR | Other SDR | Inference (RTF) |
|-------|------------|-----------|----------|-----------|-----------------|
| BS-RoFormer | **10.47** | 8.12 | 7.89 | 6.54 | 0.15x |
| MelBand RoFormer | 10.31 | 8.24 | **8.02** | 6.61 | 0.14x |
| BSMamba2 | 10.12 | 7.95 | 7.76 | 6.42 | 0.12x |
| HT Demucs v4 | 9.00 | **8.45** | 7.51 | **6.82** | 0.18x |
| Band-SCNet | 8.85 | 7.62 | 7.23 | 5.98 | **0.05x** |
| SCNet | 8.51 | 7.45 | 7.12 | 5.87 | 0.08x |

**Key Insights (2025 Benchmark Paper):**
- SDR remains best metric for vocals
- SI-SAR outperforms SDR/SAR for drums and bass evaluation
- MelBand RoFormer selected 97% of time in ensemble voting for vocals

---

## Hindi Music-Specific Considerations

### Unique Challenges

| Challenge | Description | Impact on Separation |
|-----------|-------------|---------------------|
| **Tanpura Drone** | Continuous harmonic drone throughout song | Bleeds into vocal stem, masks bass frequencies |
| **Tabla/Dholak** | Complex rhythmic patterns with pitch bends | Harder to isolate than Western drums |
| **Harmonium** | Sustained chords overlapping vocals | Frequency overlap in 200-800Hz range |
| **Sitar/Sarangi** | Sympathetic strings create dense harmonics | Difficult to separate from "other" stem |
| **Gamaka Preservation** | Subtle pitch oscillations in vocals | Must not be filtered as noise/artifact |

### Recommended Preprocessing

1. **High-Pass Filter Tanpura**: Apply gentle HPF (80Hz cutoff) before separation to reduce drone interference
2. **Sample Rate**: Use 44.1kHz (not 48kHz) - most models trained on this
3. **Loudness Normalization**: -14 LUFS before processing for consistent results
4. **Chunk Length**: 10-second chunks with 1-second overlap for long songs

### Post-Processing for Hindi Music

```
Separated Vocals
    │
    ▼
┌─────────────────────────────────┐
│  De-Reverb (optional)           │  ← Remove studio/hall reverb
├─────────────────────────────────┤
│  Harmonic Repair                │  ← Fill tanpura bleed gaps
├─────────────────────────────────┤
│  High-Frequency Enhancement     │  ← Restore gamaka detail
└─────────────────────────────────┘
    │
    ▼
Clean Vocals for Transcription
```

---

## Model Selection Decision Tree

```
                    ┌─────────────────────┐
                    │  What's your goal?  │
                    └──────────┬──────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │ Best Quality │   │  Real-Time   │   │  Flexible    │
    │  (Offline)   │   │  Streaming   │   │  Prompting   │
    └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
           │                  │                  │
           ▼                  ▼                  ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │ BS-RoFormer  │   │  Band-SCNet  │   │  SAM Audio   │
    │ or MelBand   │   │              │   │  (Meta)      │
    └──────────────┘   └──────────────┘   └──────────────┘
           │
           ▼
    ┌──────────────────────────────────┐
    │  Sparse vocals / classical?      │
    │  YES → BSMamba2                  │
    │  NO  → BS-RoFormer               │
    └──────────────────────────────────┘
```

---

## Hardware Requirements

| Model | VRAM (Min) | VRAM (Recommended) | CPU Fallback | RTF (GPU) | RTF (CPU) |
|-------|------------|-------------------|--------------|-----------|-----------|
| BS-RoFormer | 6 GB | 12 GB | Slow | 0.15x | 2.5x |
| MelBand RoFormer | 6 GB | 12 GB | Slow | 0.14x | 2.3x |
| BSMamba2 | 4 GB | 8 GB | Moderate | 0.12x | 1.8x |
| HT Demucs v4 | 4 GB | 8 GB | Viable | 0.18x | 1.5x |
| Band-SCNet | 2 GB | 4 GB | Fast | 0.05x | 0.4x |
| SAM Audio | 8 GB | 16 GB | Not Recommended | 0.25x | N/A |

**RTF = Real-Time Factor** (lower is faster; <1.0 means faster than real-time)

---

## Implementation Guide

### Using `audio-separator` (Recommended Wrapper)

```python
from audio_separator.separator import Separator

separator = Separator(
    model_file_dir="/models",
    output_dir="./separated"
)

# Load BS-RoFormer model
separator.load_model(model_filename="model_bs_roformer_ep_317_sdr_10.47.ckpt")

# Separate
output_files = separator.separate("hindi_song.mp3")
# Returns: ['hindi_song_(Vocals).wav', 'hindi_song_(Instrumental).wav']
```

### Direct BS-RoFormer Usage

```python
import torch
from bs_roformer import BSRoformer
import torchaudio

model = BSRoformer(
    dim=512,
    depth=12,
    stereo=True,
    num_stems=4,
    time_transformer_depth=1,
    freq_transformer_depth=1
)

# Load pretrained weights
model.load_state_dict(torch.load("bs_roformer_weights.pt"))
model.eval()

# Process audio
audio, sr = torchaudio.load("song.wav")
with torch.no_grad():
    stems = model(audio.unsqueeze(0))  # [batch, stems, channels, samples]

vocals = stems[0, 0]  # First stem is vocals
drums = stems[0, 1]
bass = stems[0, 2]
other = stems[0, 3]
```

### Integration with Pipeline

```python
class SourceSeparator:
    def __init__(self, model_type="bs_roformer", device="cuda"):
        self.device = device
        self.model_type = model_type
        self._load_model()

    def _load_model(self):
        if self.model_type == "bs_roformer":
            from audio_separator.separator import Separator
            self.separator = Separator()
            self.separator.load_model("model_bs_roformer_ep_317_sdr_10.47.ckpt")
        elif self.model_type == "demucs":
            import demucs.api
            self.separator = demucs.api.Separator(model="htdemucs")

    def separate(self, audio_path: str) -> dict:
        if self.model_type == "bs_roformer":
            files = self.separator.separate(audio_path)
            return {"vocals": files[0], "instrumental": files[1]}
        elif self.model_type == "demucs":
            origin, separated = self.separator.separate_audio_file(audio_path)
            return {
                "vocals": separated["vocals"],
                "drums": separated["drums"],
                "bass": separated["bass"],
                "other": separated["other"]
            }

---

## Apple Silicon Optimization (M1/M2/M3)

### Compatibility Matrix

| Model | MPS Support | Unified Memory (16GB) | Unified Memory (32GB+) | Notes |
|-------|-------------|----------------------|------------------------|-------|
| **BS-RoFormer** | ✅ Full | ✅ Works | ✅ Optimal | Best choice for M1 Pro |
| MelBand RoFormer | ✅ Full | ✅ Works | ✅ Optimal | Similar to BS-RoFormer |
| BSMamba2 | ⚠️ Partial | ✅ Works | ✅ Optimal | Some ops fall back to CPU |
| HT Demucs v4 | ✅ Excellent | ✅ Works | ✅ Optimal | Best M1 optimization |
| Band-SCNet | ✅ Full | ✅ Easy | ✅ Optimal | Fastest on Apple Silicon |
| SAM Audio | ⚠️ Partial | ❌ Too tight | ⚠️ Marginal | Not recommended |

### Expected Performance (M1 Pro 16GB)

| Model | 4-min Song | RTF | Memory Usage |
|-------|------------|-----|--------------|
| BS-RoFormer | ~2-3 min | 0.5-0.8x | 8-10 GB |
| HT Demucs v4 | ~2 min | 0.4-0.6x | 6-8 GB |
| Band-SCNet | ~30 sec | 0.1-0.2x | 3-4 GB |

### Setup for Apple Silicon

```python
import torch

def get_device():
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")

device = get_device()
```

### Optimized Configuration

```python
class AppleSiliconSeparator:
    def __init__(self, model_type="bs_roformer"):
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.chunk_duration = 30  # Process in 30-sec chunks to manage memory
        self.overlap = 2  # 2-second overlap between chunks

    def separate_with_chunking(self, audio_path: str) -> dict:
        import torchaudio

        audio, sr = torchaudio.load(audio_path)
        chunk_samples = self.chunk_duration * sr
        overlap_samples = self.overlap * sr

        # Process in chunks for memory efficiency
        chunks = []
        for start in range(0, audio.shape[1], chunk_samples - overlap_samples):
            end = min(start + chunk_samples, audio.shape[1])
            chunk = audio[:, start:end]

            # Clear MPS cache between chunks
            if self.device == "mps":
                torch.mps.empty_cache()

            separated_chunk = self._process_chunk(chunk)
            chunks.append(separated_chunk)

        return self._merge_chunks(chunks, overlap_samples)
```

### Memory Management Tips

1. **Clear MPS Cache**: Call `torch.mps.empty_cache()` between operations
2. **Chunk Processing**: Split songs >3 minutes into 30-second chunks
3. **Close Other Apps**: Safari, Chrome consume significant unified memory
4. **Use float32**: MPS has better float32 support than float16

```python
# Memory cleanup after separation
torch.mps.empty_cache()
import gc
gc.collect()
```

### Known Issues & Workarounds

| Issue | Workaround |
|-------|------------|
| MPS out of memory | Reduce chunk size to 20 seconds |
| Slow first inference | Warm-up run with short audio clip |
| Some ops unsupported | Set `PYTORCH_ENABLE_MPS_FALLBACK=1` env var |
| Inconsistent results | Use `torch.manual_seed()` for reproducibility |

```bash
# Enable CPU fallback for unsupported MPS operations
export PYTORCH_ENABLE_MPS_FALLBACK=1
```

### Recommended Model for M1 Pro 16GB

**Primary: BS-RoFormer** with chunked processing
- Best vocal quality for gamaka preservation
- Manageable memory footprint with 30-sec chunks
- ~2-3 minutes for a typical Bollywood song

**Fallback: HT Demucs v4**
- Excellent M1 optimization by Meta
- Slightly lower vocal SDR but faster
- Better for batch processing multiple songs

