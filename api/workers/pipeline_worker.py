from pathlib import Path
from sqlalchemy.orm import Session

from src.source_separation import (
    SeparationConfig,
    AppleSiliconSeparator,
    save_stems_as_mp3,
    copy_original_audio,
)
from src.vocal_transcription import VocalTranscriber, TranscriptionConfig
from src.vocal_transcription.frame_exporter import export_processed_frames
from src.chord_detection import ChordDetector, ChordDetectionConfig

from api.database.models import ProcessingStage
from api.services.progress_tracker import ProgressTracker
from api.services.job_manager import JobManager
from api.config import settings
from api.utils.logging import get_logger

logger = get_logger("pipeline_worker")


class PipelineWorker:
    
    def __init__(self, db: Session, job_id: str):
        self.db = db
        self.job_id = job_id
        self.progress_tracker = ProgressTracker(db, job_id)
        self.job_storage_path = settings.get_job_storage_path(job_id)
        
        self.input_dir = self.job_storage_path / "input"
        self.separated_dir = self.job_storage_path / "separated"
        self.transcription_dir = self.job_storage_path / "transcription"
        self.chords_dir = self.job_storage_path / "chords"
        
        self._create_directories()
    
    def _create_directories(self):
        for directory in [self.input_dir, self.separated_dir, self.transcription_dir, self.chords_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def run(self, input_audio_path: Path):
        try:
            logger.info(f"Starting pipeline for job {self.job_id}")
            
            stems = self._run_separation(input_audio_path)
            
            transcription_result = self._run_transcription(
                stems.get("vocals"),
                input_audio_path
            )
            
            chord_progression = self._run_chord_detection(
                stems.get("bass"),
                stems.get("other"),
                stems.get("instrumental"),
                transcription_result.get("tempo_bpm")
            )
            
            self.progress_tracker.complete_job()
            logger.info(f"Pipeline completed successfully for job {self.job_id}")
            
        except Exception as e:
            logger.error(f"Pipeline failed for job {self.job_id}: {str(e)}", exc_info=True)
            self.progress_tracker.fail_job(str(e))
            raise
    
    def _run_separation(self, input_audio_path: Path) -> dict:
        logger.info(f"Stage 1: Source Separation for job {self.job_id}")
        self.progress_tracker.start_separation("Initializing source separation")

        config = SeparationConfig(
            output_dir=self.separated_dir,
            device="auto"
        )
        separator = AppleSiliconSeparator(config)

        def separation_progress_callback(progress: int, message: str):
            self.progress_tracker.update_separation(progress, message)

        stems = separator.separate(input_audio_path, progress_callback=separation_progress_callback)

        self.progress_tracker.update_separation(70, "Saving separated stems as MP3 files")
        base_filename = f"{self.job_id}_{input_audio_path.stem}"
        stem_paths = save_stems_as_mp3(
            stems=stems,
            output_dir=self.separated_dir,
            base_filename=base_filename,
            sample_rate=config.sample_rate,
            bitrate="320k",
            verbose=False
        )

        self.progress_tracker.update_separation(90, "Copying original audio file")
        original_path = copy_original_audio(
            input_audio_path=input_audio_path,
            output_dir=self.separated_dir,
            output_format="mp3",
            bitrate="320k",
            verbose=False,
            base_filename=base_filename
        )

        if original_path:
            stem_paths["original"] = original_path
            logger.info(f"Original audio saved as MP3: {original_path}")

        stem_paths_dict = {k: str(v) for k, v in stem_paths.items() if k != "original"}
        JobManager.update_file_paths(
            self.db,
            self.job_id,
            original_mp3_path=str(original_path) if original_path else None,
            stem_paths=stem_paths_dict
        )

        self.progress_tracker.complete_separation(f"Separated into {len(stem_paths)} stems successfully")
        logger.info(f"Separation complete: {len(stem_paths)} stems saved")

        return stem_paths
    
    def _run_transcription(self, vocals_path: Path, original_audio_path: Path) -> dict:
        logger.info(f"Stage 2: Vocal Transcription for job {self.job_id}")
        self.progress_tracker.start_transcription("Loading vocal track and initializing transcription model")

        config = TranscriptionConfig(
            hop_size_ms=10,
            confidence_threshold=0.6,
            device="auto"
        )
        transcriber = VocalTranscriber(config)

        self.progress_tracker.update_transcription(20, "Analyzing pitch and extracting vocal melody")
        result = transcriber.transcribe(
            audio_path=vocals_path,
            original_audio_path=original_audio_path,
            output_dir=self.transcription_dir
        )

        self.progress_tracker.update_transcription(80, "Exporting processed frames and metadata")
        frames_output_path = self.transcription_dir / f"{self.job_id}_processed_frames.json"
        export_processed_frames(
            processed_frames=result.pitch_contour,
            output_path=frames_output_path,
            original_song_path=original_audio_path,
            vocal_file_path=vocals_path,
            bpm=result.tempo_bpm
        )

        JobManager.update_job_metadata(
            self.db,
            self.job_id,
            duration=result.duration,
            tempo_bpm=result.tempo_bpm,
            num_frames=len(result.pitch_contour)
        )

        JobManager.update_file_paths(
            self.db,
            self.job_id,
            frames_json_path=str(frames_output_path)
        )

        self.progress_tracker.complete_transcription(f"Transcribed {len(result.pitch_contour)} frames at {result.tempo_bpm:.1f} BPM")
        logger.info(f"Transcription complete: {len(result.pitch_contour)} frames")

        return {
            "tempo_bpm": result.tempo_bpm,
            "duration": result.duration,
            "num_frames": len(result.pitch_contour)
        }
    
    def _run_chord_detection(self, bass_path: Path, other_path: Path, instrumental_path: Path, tempo_bpm: float) -> dict:
        logger.info(f"Stage 3: Chord Detection for job {self.job_id}")
        self.progress_tracker.start_chords("Loading BTC chord detection model")

        config = ChordDetectionConfig(
            model_path=str(settings.chord_model_path),
            bass_weight=0.5,
            other_weight=0.5,
            device="auto"
        )
        detector = ChordDetector(config)

        logger.info(f"Loading BTC model from: {settings.chord_model_path}")
        self.progress_tracker.update_chords(15, "Model loaded, analyzing harmonic content")
        detector.load_model()

        self.progress_tracker.update_chords(30, "Detecting chord progressions from stems")
        progression = detector.detect_from_stems(
            bass_path=bass_path,
            other_path=other_path,
            instrumental_path=instrumental_path,
            tempo_bpm=tempo_bpm
        )

        self.progress_tracker.update_chords(85, "Saving chord progression data")
        chords_output_path = self.chords_dir / f"{self.job_id}_chords.json"
        detector.save_json(progression, chords_output_path)

        JobManager.update_job_metadata(
            self.db,
            self.job_id,
            num_chords=len(progression.chords)
        )

        JobManager.update_file_paths(
            self.db,
            self.job_id,
            chords_json_path=str(chords_output_path)
        )

        self.progress_tracker.complete_chords(f"Detected {len(progression.chords)} chords successfully")
        logger.info(f"Chord detection complete: {len(progression.chords)} chords")

        return {
            "num_chords": len(progression.chords),
            "duration": progression.duration
        }

