import json
import logging
from pathlib import Path

from .config import TranscriptionConfig
from .constants import SAMPLE_RATE, DEFAULT_TEMPO_BPM
from .models import TranscriptionResult
from .pitch_detector import PitchDetector
from .pitch_processor import PitchProcessor
from .note_segmenter import NoteSegmenter
from .midi_generator import MidiGenerator
from .visualizer import PitchVisualizer
from .audio_trimmer import AudioTrimmer
from .custom_algo import FrequencySmoothing
from .frame_exporter import export_processed_frames

logger = logging.getLogger(__name__)


class VocalTranscriber:
    def __init__(self, config: TranscriptionConfig | None = None):
        self.config = config or TranscriptionConfig()

        self.audio_trimmer = AudioTrimmer(self.config)
        self.pitch_detector = PitchDetector(self.config)
        self.frequency_smoothing = FrequencySmoothing(threshold_hz=2.0)
        self.pitch_processor = PitchProcessor(self.config)
        self.note_segmenter = NoteSegmenter(self.config)
        self.midi_generator = MidiGenerator(self.config)

        logger.info(f"VocalTranscriber initialized with device: {self.config.get_device()}")

    def transcribe(
        self,
        audio_path: str | Path,
        original_audio_path: str | Path | None = None,
        output_dir: str | Path | None = None,
    ) -> TranscriptionResult:
        audio_path = Path(audio_path)
        logger.info(f"Transcribing: {audio_path}")

        audio, sr, duration = self.audio_trimmer.load_and_trim(audio_path)

        if original_audio_path:
            from .tempo_detector import TempoDetector
            logger.info("Detecting tempo from original audio...")
            tempo_detector = TempoDetector()
            tempo_bpm = tempo_detector.detect(original_audio_path)
            logger.info(f"Detected tempo: {tempo_bpm:.1f} BPM")
        else:
            tempo_bpm = DEFAULT_TEMPO_BPM
            logger.info(f"Using default tempo: {tempo_bpm} BPM")

        logger.info("Step 1/5: Detecting pitch...")
        raw_frames = self.pitch_detector.detect_from_tensor(audio, sr)

        logger.info("Step 3/5: Processing pitch contour...")
        processed_frames = self.pitch_processor.process(raw_frames)

        if output_dir:
            output_dir = Path(output_dir)
            frames_json_path = output_dir / f"{audio_path.stem}_processed_frames.json"
        else:
            frames_json_path = audio_path.parent / f"{audio_path.stem}_processed_frames.json"

        export_processed_frames(
            processed_frames=processed_frames,
            output_path=frames_json_path,
            original_song_path=original_audio_path,
            vocal_file_path=audio_path,
            bpm=tempo_bpm,
        )

        viewer_path = Path("/Users/psarthak/personal/projects/music-transcription-viewer/vocal_pitch_viewer/web/sample_data/pitch_data.json")
        viewer_path.parent.mkdir(parents=True, exist_ok=True)
        export_processed_frames(
            processed_frames=processed_frames,
            output_path=viewer_path,
            original_song_path=original_audio_path,
            vocal_file_path=audio_path,
            bpm=tempo_bpm,
        )
        logger.info(f"Also saved processed frames to viewer location: {viewer_path}")

        logger.info("Step 4/5: Detecting key and scale...")
        from .key_detector import KeyScaleDetector
        key_detector = KeyScaleDetector(self.config)
        key_info = key_detector.detect(processed_frames)

        logger.info("Step 5/5: Segmenting into notes...")
        notes = self.note_segmenter.segment(processed_frames)

        # visualizer = PitchVisualizer()
        # if output_dir:
        #     viz_path = output_dir / f"{audio_path.stem}_pitch_analysis.png"
        # else:
        #     viz_path = audio_path.parent / f"{audio_path.stem}_pitch_analysis.png"
        # visualizer.plot_processed_frames(processed_frames, notes=notes, output_path=viz_path, show=False)
        # logger.info(f"Saved pitch visualization to {viz_path}")

        # if output_dir:
        #     key_viz_path = output_dir / f"{audio_path.stem}_key_analysis.png"
        # else:
        #     key_viz_path = audio_path.parent / f"{audio_path.stem}_key_analysis.png"
        # visualizer.plot_key_analysis(processed_frames, key_info, output_path=key_viz_path, show=False)
        # logger.info(f"Saved key analysis visualization to {key_viz_path}")

        result = TranscriptionResult(
            notes=notes,
            pitch_contour=processed_frames,
            tempo_bpm=tempo_bpm,
            duration=duration,
            sample_rate=SAMPLE_RATE,
            key_info=key_info,
        )

        logger.info(f"Transcription complete: {len(notes)} notes | Key: {key_info.tonic_name} {key_info.scale_type} (confidence: {key_info.confidence:.2f})")
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

        if result.key_info:
            data["key_info"] = {
                "tonic_midi": result.key_info.tonic_midi,
                "tonic_frequency": result.key_info.tonic_frequency,
                "tonic_name": result.key_info.tonic_name,
                "scale_type": result.key_info.scale_type,
                "scale_intervals": result.key_info.scale_intervals,
                "confidence": result.key_info.confidence,
                "detected_notes": result.key_info.detected_notes,
                "swara_usage": result.key_info.swara_usage,
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

