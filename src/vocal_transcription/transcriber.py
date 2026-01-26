import json
import logging
from pathlib import Path

import torchaudio

from .config import TranscriptionConfig
from .constants import SAMPLE_RATE, DEFAULT_TEMPO_BPM
from .models import TranscriptionResult
from .pitch_detector import PitchDetector
from .pitch_processor import PitchProcessor
from .note_segmenter import NoteSegmenter
from .midi_generator import MidiGenerator
from .visualizer import PitchVisualizer

logger = logging.getLogger(__name__)


class VocalTranscriber:
    def __init__(self, config: TranscriptionConfig | None = None):
        self.config = config or TranscriptionConfig()

        self.pitch_detector = PitchDetector(self.config)
        self.pitch_processor = PitchProcessor(self.config)
        self.note_segmenter = NoteSegmenter(self.config)
        self.midi_generator = MidiGenerator(self.config)

        logger.info(f"VocalTranscriber initialized with device: {self.config.get_device()}")

    def transcribe(self, audio_path: str | Path, original_audio_path: str | Path | None = None) -> TranscriptionResult:
        audio_path = Path(audio_path)
        logger.info(f"Transcribing: {audio_path}")

        audio, sr = torchaudio.load(str(audio_path))
        duration = audio.shape[1] / sr

        if original_audio_path:
            from .tempo_detector import TempoDetector
            logger.info("Detecting tempo from original audio...")
            tempo_detector = TempoDetector()
            tempo_bpm = tempo_detector.detect(original_audio_path)
            logger.info(f"Detected tempo: {tempo_bpm:.1f} BPM")
        else:
            tempo_bpm = DEFAULT_TEMPO_BPM
            logger.info(f"Using default tempo: {tempo_bpm} BPM")

        logger.info("Step 1/3: Detecting pitch...")
        raw_frames = self.pitch_detector.detect(audio_path)

        logger.info("Step 2/3: Processing pitch contour...")
        processed_frames = self.pitch_processor.process(raw_frames)

        visualizer = PitchVisualizer()
        viz_path = audio_path.parent / f"{audio_path.stem}_pitch_analysis.png"
        visualizer.plot_processed_frames(processed_frames, output_path=viz_path, show=False)
        logger.info(f"Saved pitch visualization to {viz_path}")

        logger.info("Step 3/3: Segmenting into notes...")
        notes = self.note_segmenter.segment(processed_frames)

        result = TranscriptionResult(
            notes=notes,
            pitch_contour=processed_frames,
            tempo_bpm=tempo_bpm,
            duration=duration,
            sample_rate=SAMPLE_RATE,
        )

        logger.info(f"Transcription complete: {len(notes)} notes")
        return result

    def save_midi(self, result: TranscriptionResult, output_path: str | Path) -> Path:
        return self.midi_generator.generate(result, output_path)

    def export_json(self, result: TranscriptionResult, output_path: str | Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "duration": result.duration,
            "tempo_bpm": result.tempo_bpm,
            "sample_rate": result.sample_rate,
            "notes": [
                {
                    "start_time": n.start_time,
                    "end_time": n.end_time,
                    "anchor_midi": n.anchor_midi,
                    "velocity": n.velocity,
                    "duration": n.duration,
                }
                for n in result.notes
            ],
        }

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported JSON to {output_path}")
        return output_path

    def export_pitch_csv(self, result: TranscriptionResult, output_path: str | Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write("time,frequency,midi_pitch,confidence,voiced\n")
            for frame in result.pitch_contour:
                voiced = 1 if frame.is_voiced else 0
                f.write(f"{frame.time:.4f},{frame.frequency:.2f},{frame.midi_pitch:.2f},{frame.confidence:.4f},{voiced}\n")

        logger.info(f"Exported pitch CSV to {output_path}")
        return output_path

