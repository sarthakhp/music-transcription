import logging
from pathlib import Path

from .config import ChordDetectionConfig
from .models import ChordProgression
from .stem_mixer import StemMixer
from .btc_model import BTCModel
from .post_processor import ChordPostProcessor
from .exporter import ChordExporter

logger = logging.getLogger(__name__)


class ChordDetector:
    def __init__(self, config: ChordDetectionConfig | None = None):
        self.config = config or ChordDetectionConfig()
        
        self.stem_mixer = StemMixer(self.config)
        self.btc_model = BTCModel(self.config)
        self.post_processor = ChordPostProcessor(self.config)
        self.exporter = ChordExporter()
        
        logger.info(f"ChordDetector initialized with device: {self.config.get_device()}")

    def load_model(self, model_path: str | Path | None = None):
        self.btc_model.load_model(model_path)
        logger.info("BTC model loaded successfully")

    def detect_from_stems(
        self,
        bass_path: str | Path | None = None,
        other_path: str | Path | None = None,
        instrumental_path: str | Path | None = None,
        tempo_bpm: float = 120.0,
        key_info: dict | None = None,
    ) -> ChordProgression:
        logger.info("Starting chord detection from stems")
        if bass_path:
            logger.info(f"Bass: {bass_path}")
        if other_path:
            logger.info(f"Other: {other_path}")
        if instrumental_path:
            logger.info(f"Instrumental: {instrumental_path}")

        mixed_audio, sr = self.stem_mixer.mix_stems(
            bass_path=bass_path,
            other_path=other_path,
            instrumental_path=instrumental_path,
        )

        logger.info("Running BTC model inference...")
        raw_predictions = self.btc_model.predict(mixed_audio, sr)

        logger.info("Post-processing predictions...")
        chords = self.post_processor.process(raw_predictions)

        duration = len(mixed_audio) / sr
        progression = ChordProgression(
            chords=chords,
            duration=duration,
            sample_rate=sr,
            tempo_bpm=tempo_bpm,
            key_info=key_info or {},
        )

        logger.info(f"Chord detection complete: {len(chords)} chords over {duration:.2f}s")
        return progression

    def save_json(self, progression: ChordProgression, output_path: str | Path) -> None:
        self.exporter.export_json(progression, output_path)

    def save_lab(self, progression: ChordProgression, output_path: str | Path) -> None:
        self.exporter.export_lab(progression, output_path)

    def save_csv(self, progression: ChordProgression, output_path: str | Path) -> None:
        self.exporter.export_csv(progression, output_path)

