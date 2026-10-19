"""Robust global tempo estimation using only numpy and librosa.

librosa's default ``beat_track`` picks one autocorrelation peak and is prone to
octave errors (half/double) and 3:2 errors. This estimator instead:

1. builds several onset-strength envelopes (full band, percussive, low band),
2. averages their tempograms over the whole song for a stable periodicity curve,
3. scores each candidate tempo by how much support it has at its musical
   multiples (x1/2, x1, x2, x3/2, x3) and weights it with a gentle prior around
   typical song tempi so octave ties resolve to the natural tapping rate,
4. refines the winner from the actual beat grid for sub-BPM precision.
"""
import logging

import numpy as np

logger = logging.getLogger(__name__)

MIN_BPM = 50.0
MAX_BPM = 210.0
_PRIOR_CENTER_BPM = 110.0
_PRIOR_SIGMA_OCTAVES = 0.9
_MAX_SECONDS = 240
_SR = 22050
_HOP = 512


def _prior(bpm: np.ndarray) -> np.ndarray:
    octaves = np.log2(bpm / _PRIOR_CENTER_BPM)
    return np.exp(-0.5 * (octaves / _PRIOR_SIGMA_OCTAVES) ** 2)


def _envelopes(y: np.ndarray, sr: int) -> list[np.ndarray]:
    import librosa

    harmonic, percussive = librosa.effects.hpss(y, margin=2.0)
    del harmonic
    full = librosa.onset.onset_strength(y=y, sr=sr, hop_length=_HOP, aggregate=np.median)
    perc = librosa.onset.onset_strength(y=percussive, sr=sr, hop_length=_HOP)
    mel = librosa.feature.melspectrogram(y=y, sr=sr, hop_length=_HOP, n_mels=64, fmax=250)
    low = librosa.onset.onset_strength(S=librosa.power_to_db(mel), sr=sr, hop_length=_HOP)
    return [e for e in (full, perc, low) if np.any(e > 0)]


def _periodicity(envelopes: list[np.ndarray], sr: int, bpms: np.ndarray) -> np.ndarray:
    import librosa

    curves = []
    for env in envelopes:
        tg = librosa.feature.tempogram(onset_envelope=env, sr=sr, hop_length=_HOP, win_length=768)
        freqs = librosa.tempo_frequencies(tg.shape[0], sr=sr, hop_length=_HOP)
        mean = tg.mean(axis=1)
        mean = np.clip(mean - np.median(mean), 0, None)
        curve = np.interp(bpms, freqs[1:][::-1], mean[1:][::-1])
        peak = curve.max()
        if peak > 0:
            curves.append(curve / peak)
    return np.mean(curves, axis=0) if curves else np.zeros_like(bpms)


def _score(curve: np.ndarray, bpms: np.ndarray) -> np.ndarray:
    def at(mult: float) -> np.ndarray:
        return np.interp(bpms * mult, bpms, curve, left=0.0, right=0.0)

    support = at(1.0) + 0.5 * at(2.0) + 0.5 * at(0.5) + 0.25 * at(1.5) + 0.25 * at(3.0)
    return support * _prior(bpms)


def _refine(y: np.ndarray, sr: int, bpm: float) -> float:
    """Snap to the median inter-beat interval of a grid anchored at ``bpm``."""
    import librosa

    _, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=_HOP, start_bpm=bpm, tightness=200)
    times = librosa.frames_to_time(beats, sr=sr, hop_length=_HOP)
    if len(times) < 8:
        return bpm
    # Least-squares slope over beat index is robust to a few missed beats.
    idx = np.round((times - times[0]) / (60.0 / bpm))
    slope = np.polyfit(idx, times, 1)[0]
    refined = 60.0 / slope
    return float(refined) if abs(refined - bpm) / bpm < 0.04 else bpm


def estimate_tempo(audio_path: str) -> float | None:
    import librosa

    y, sr = librosa.load(audio_path, sr=_SR, mono=True, duration=_MAX_SECONDS)
    if len(y) < sr * 5 or not np.any(y):
        return None
    bpms = np.arange(MIN_BPM, MAX_BPM, 0.25)
    curve = _periodicity(_envelopes(y, sr), sr, bpms)
    if not np.any(curve):
        return None
    best = float(bpms[int(np.argmax(_score(curve, bpms)))])
    tempo = round(_refine(y, sr, best), 1)
    logger.info(f"Estimated tempo {tempo} BPM (candidate {best})")
    return tempo
