from pathlib import Path
from sqlalchemy.orm import Session

from src.source_separation import (
    AudioSeparator,
    SeparationConfig,
    save_stems_as_mp3,
    copy_original_audio,
)
from src.vocal_transcription import VocalTranscriber, TranscriptionConfig
from src.vocal_transcription.frame_exporter import export_processed_frames
from src.instrument_transcription import (
    InstrumentTranscriptionConfig,
    InstrumentTranscriptionResult,
    BassTranscriber,
    MelodicTranscriber,
)
from src.instrument_transcription.exporter import export_instrument_transcription
from src.chord_detection import ChordDetector, ChordDetectionConfig

from api.database.models import ProcessingStage
from api.services.progress_tracker import ProgressTracker
from api.services.job_manager import JobManager
from api.config import settings
from api.utils.logging import get_logger

logger = get_logger("pipeline_worker")


class PipelineWorker:
    
    def __init__(self, db: Session, job_id: str, separation_config: SeparationConfig | None = None):
        self.db = db
        self.job_id = job_id
        self.separation_config = separation_config or SeparationConfig()
        self.progress_tracker = ProgressTracker(db, job_id)
        self.job_storage_path = settings.get_job_storage_path(job_id)
        
        self.input_dir = self.job_storage_path / "input"
        self.separated_dir = self.job_storage_path / "separated"
        self.transcription_dir = self.job_storage_path / "transcription"
        self.instruments_dir = self.job_storage_path / "instruments"
        self.chords_dir = self.job_storage_path / "chords"

        self._create_directories()

    def _create_directories(self):
        for directory in [self.input_dir, self.separated_dir, self.transcription_dir, self.instruments_dir, self.chords_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def run(
        self,
        input_audio_path: Path | None = None,
        source_url: str | None = None,
        start_time: float | None = None,
        end_time: float | None = None,
    ):
        try:
            logger.info(f"Starting pipeline for job {self.job_id}")

            # Stage 0: Download (URL jobs only)
            if source_url:
                input_audio_path = self._run_download(source_url, start_time, end_time)

            stems = self._run_separation(input_audio_path)
            
            transcription_result = self._run_transcription(
                stems.get("vocals"),
                input_audio_path
            )

            # For 2-stem models (vocals + instrumental), the instrumental
            # stem contains everything non-vocal. Use it as the "other" stem
            # fallback for instrument transcription.
            bass_stem = stems.get("bass")
            other_stem = stems.get("other") or stems.get("instrumental")

            instrument_result = self._run_instrument_transcription(
                bass_stem,
                other_stem,
                transcription_result.get("tempo_bpm"),
            )

            chord_progression = self._run_chord_detection(
                stems.get("bass"),
                stems.get("other"),
                stems.get("instrumental"),
                transcription_result.get("tempo_bpm")
            )
            
            self.progress_tracker.complete_job()
            logger.info(f"Pipeline completed successfully for job {self.job_id}")

            # Best-effort publish to remote storage so the hosted viewer can
            # read this job from anywhere. Never fails the job.
            from api.services.storage_publisher import try_publish_job
            try_publish_job(self.db, self.job_id)

        except Exception as e:
            logger.error(f"Pipeline failed for job {self.job_id}: {str(e)}", exc_info=True)
            self.progress_tracker.fail_job(str(e))
            raise
    
    def _run_download(
        self,
        source_url: str,
        start_time: float | None,
        end_time: float | None,
    ) -> Path:
        logger.info(f"Stage 0: Download for job {self.job_id} — {source_url}")
        # Model-setup already claimed this stage's leading 0-20% (see
        # run_pipeline_task) — continue from there instead of resetting to 0,
        # which would visibly rewind the progress bar.
        self.progress_tracker.update_download(20, "Connecting to download source")

        from api.services.youtube_downloader import download_audio, UnsupportedURLError

        def download_progress(progress: int, message: str):
            from api.database.session import SessionLocal
            db = SessionLocal()
            try:
                scaled = int(20 + progress * 0.8)
                ProgressTracker(db, self.job_id).update_download(scaled, message)
            finally:
                db.close()

        try:
            audio_path = download_audio(
                url=source_url,
                output_dir=self.input_dir,
                progress_callback=download_progress,
                start_time=start_time,
                end_time=end_time,
            )
        except UnsupportedURLError as e:
            raise RuntimeError(str(e)) from e

        # Update file size now that we know it
        file_size = audio_path.stat().st_size
        JobManager.update_file_paths(
            self.db, self.job_id, input_file_path=str(audio_path)
        )
        job = JobManager.get_job(self.db, self.job_id)
        job.file_size = file_size
        self.db.commit()

        self.progress_tracker.complete_download(
            f"Downloaded: {audio_path.name} ({file_size // 1024}KB)"
        )
        logger.info(f"Download complete: {audio_path}")
        return audio_path

    def _run_separation(self, input_audio_path: Path) -> dict:
        logger.info(
            f"Stage 1: Source Separation for job {self.job_id} "
            f"(model={self.separation_config.model_key})"
        )
        # For upload jobs, model-setup already claimed this stage's leading
        # 0-20% (see run_pipeline_task) — continue from there instead of
        # resetting to 0. For URL jobs this stage hasn't been touched yet
        # (model-setup went to the DOWNLOAD stage instead), so this just
        # advances it a little early, which is harmless.
        self.progress_tracker.update_separation(20, "Initializing source separation")

        separator = AudioSeparator(self.separation_config)

        def separation_progress_callback(progress: int, message: str):
            from api.database.session import SessionLocal
            db = SessionLocal()
            try:
                # Compressed into 20-90 (not 20-100) so the post-processing
                # milestones below (saving stems, copying original) have
                # their own headroom and the bar never rewinds.
                scaled = int(20 + progress * 0.7)
                ProgressTracker(db, self.job_id).update_separation(scaled, message)
            finally:
                db.close()

        stems = separator.separate(
            input_audio_path,
            output_dir=self.separated_dir,
            progress_callback=separation_progress_callback,
        )

        self.progress_tracker.update_separation(90, "Saving separated stems as MP3 files")
        base_filename = f"{self.job_id}_{input_audio_path.stem}"
        stem_paths = save_stems_as_mp3(
            stems=stems,
            output_dir=self.separated_dir,
            base_filename=base_filename,
            sample_rate=self.separation_config.sample_rate,
            bitrate="320k",
            verbose=False
        )

        self.progress_tracker.update_separation(95, "Copying original audio file")
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
    
    def _run_transcription(self, vocals_path: Path | None, original_audio_path: Path) -> dict:
        logger.info(f"Stage 2: Vocal Transcription for job {self.job_id}")

        if vocals_path is None:
            logger.warning(f"No vocals stem for job {self.job_id}; detecting tempo from original audio only")
            self.progress_tracker.start_transcription("No vocals detected — detecting tempo from full mix")
            from src.vocal_transcription.tempo_detector import TempoDetector
            from src.vocal_transcription.constants import DEFAULT_TEMPO_BPM
            import soundfile as sf
            try:
                tempo_bpm = TempoDetector().detect(original_audio_path)
            except Exception:
                tempo_bpm = DEFAULT_TEMPO_BPM
            sf_info = sf.info(str(original_audio_path))
            duration = sf_info.duration
            JobManager.update_job_metadata(
                self.db, self.job_id,
                duration=duration, tempo_bpm=tempo_bpm, num_frames=0
            )
            self.progress_tracker.complete_transcription(f"Tempo detected: {tempo_bpm:.1f} BPM (no vocals)")
            return {"tempo_bpm": tempo_bpm, "duration": duration, "num_frames": 0}

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
    
    def _run_instrument_transcription(
        self, bass_path: Path | None, other_path: Path | None, tempo_bpm: float | None
    ) -> dict:
        logger.info(f"Stage 3: Instrument Transcription for job {self.job_id}")
        self.progress_tracker.start_instruments("Initializing instrument transcription")

        config = InstrumentTranscriptionConfig()
        result = InstrumentTranscriptionResult()

        # Transcribe bass stem
        if bass_path and Path(bass_path).exists():
            self.progress_tracker.update_instruments(10, "Transcribing bass line")
            bass_transcriber = BassTranscriber(config)
            result.tracks["bass"] = bass_transcriber.transcribe(bass_path)
        else:
            logger.warning(f"Bass stem not found for job {self.job_id}, skipping bass transcription")

        # Transcribe "other" stem (guitars, keys, synths)
        if other_path and Path(other_path).exists():
            self.progress_tracker.update_instruments(50, "Transcribing melodic instruments")
            melodic_transcriber = MelodicTranscriber(config)
            result.tracks["other"] = melodic_transcriber.transcribe(other_path)
        else:
            logger.warning(f"Other stem not found for job {self.job_id}, skipping melodic transcription")

        result.duration = max(
            (track.duration for track in result.tracks.values()), default=0.0
        )

        # Export results
        self.progress_tracker.update_instruments(85, "Saving instrument transcription data")
        instruments_output_path = self.instruments_dir / f"{self.job_id}_instruments.json"
        export_instrument_transcription(result, instruments_output_path, tempo_bpm=tempo_bpm)

        JobManager.update_file_paths(
            self.db,
            self.job_id,
            instruments_json_path=str(instruments_output_path),
        )

        self.progress_tracker.complete_instruments(
            f"Transcribed {result.total_notes} notes across {len(result.tracks)} instrument(s)"
        )
        logger.info(f"Instrument transcription complete: {result.total_notes} notes")

        return {
            "total_notes": result.total_notes,
            "tracks": list(result.tracks.keys()),
            "duration": result.duration,
        }

    def _run_chord_detection(self, bass_path: Path, other_path: Path, instrumental_path: Path, tempo_bpm: float) -> dict:
        logger.info(f"Stage 4: Chord Detection for job {self.job_id}")
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

