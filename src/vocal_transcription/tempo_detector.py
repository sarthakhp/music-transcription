import logging
from pathlib import Path

import numpy as np

from .constants import DEFAULT_TEMPO_BPM

logger = logging.getLogger(__name__)


class TempoDetector:
    def __init__(self):
        self._estimator = None

    def _get_estimator(self):
        if self._estimator is None:
            try:
                from BeatNet.BeatNet import BeatNet
                self._estimator = BeatNet(
                    1,
                    mode='offline',
                    inference_model='DBN',
                    plot=[],
                    thread=False
                )
            except ImportError:
                logger.warning("BeatNet not installed. Install with: pip install BeatNet")
                raise
        return self._estimator

    def _detect_with_beatnet(self, audio_path: str) -> float | None:
        try:
            estimator = self._get_estimator()
            output = estimator.process(audio_path)

            if output is None or len(output) < 2:
                logger.warning("BeatNet returned insufficient beats")
                return None

            beat_times = output[:, 0]
            intervals = np.diff(beat_times)

            if len(intervals) == 0:
                logger.warning("No beat intervals detected")
                return None

            valid_intervals = intervals[(intervals > 0.2) & (intervals < 2.0)]

            if len(valid_intervals) == 0:
                logger.warning("No valid beat intervals")
                return None

            median_interval = np.median(valid_intervals)
            tempo = 60.0 / median_interval

            if tempo < 40 or tempo > 240:
                logger.warning(f"BeatNet tempo {tempo:.1f} BPM out of range")
                return None

            logger.info(f"Detected tempo (BeatNet): {tempo:.1f} BPM from {len(beat_times)} beats")
            return float(tempo)
        except Exception as e:
            logger.debug(f"BeatNet failed: {e}")
            return None

    def _detect_with_librosa(self, audio_path: str) -> float | None:
        try:
            import librosa
            y, sr = librosa.load(audio_path, sr=None)
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

            tempo_val = float(tempo) if np.isscalar(tempo) else float(tempo[0])

            if tempo_val < 40 or tempo_val > 240:
                logger.warning(f"librosa tempo {tempo_val:.1f} BPM out of range")
                return None

            logger.info(f"Detected tempo (librosa): {tempo_val:.1f} BPM")
            return tempo_val
        except Exception as e:
            logger.debug(f"librosa failed: {e}")
            return None

    def detect(self, audio_path: str | Path) -> float:
        audio_path = str(audio_path)

        tempo = self._detect_with_beatnet(audio_path)
        if tempo is not None:
            return tempo

        logger.info("Falling back to librosa for tempo detection...")
        tempo = self._detect_with_librosa(audio_path)
        if tempo is not None:
            return tempo

        logger.warning("All tempo detection methods failed, using default tempo")
        return DEFAULT_TEMPO_BPM

