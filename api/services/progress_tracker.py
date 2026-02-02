from typing import Callable, Optional
from sqlalchemy.orm import Session

from api.database.models import ProcessingStage, JobStatus
from api.services.job_manager import JobManager
from api.utils.logging import get_logger

logger = get_logger("progress_tracker")


class ProgressTracker:
    
    def __init__(self, db: Session, job_id: str):
        self.db = db
        self.job_id = job_id
        self._stage_weights = {
            ProcessingStage.SEPARATION: (0, 33),
            ProcessingStage.TRANSCRIPTION: (33, 66),
            ProcessingStage.CHORDS: (66, 100)
        }
    
    def update_stage(self, stage: ProcessingStage, stage_progress: int = 0, message: Optional[str] = None):
        start, end = self._stage_weights[stage]
        overall_progress = start + int((end - start) * (stage_progress / 100))
        overall_progress = min(max(overall_progress, 0), 100)

        JobManager.update_job_stage(
            self.db,
            self.job_id,
            stage,
            overall_progress,
            message
        )

        logger.info(f"Job {self.job_id}: {stage.value} - {stage_progress}% (overall: {overall_progress}%)")
    
    def start_separation(self, message: str = "Starting source separation"):
        JobManager.update_job_status(self.db, self.job_id, JobStatus.PROCESSING)
        self.update_stage(ProcessingStage.SEPARATION, 0, message)

    def update_separation(self, progress: int, message: Optional[str] = None):
        self.update_stage(ProcessingStage.SEPARATION, progress, message)

    def complete_separation(self, message: str = "Source separation completed"):
        self.update_stage(ProcessingStage.SEPARATION, 100, message)

    def start_transcription(self, message: str = "Starting vocal transcription"):
        self.update_stage(ProcessingStage.TRANSCRIPTION, 0, message)

    def update_transcription(self, progress: int, message: Optional[str] = None):
        self.update_stage(ProcessingStage.TRANSCRIPTION, progress, message)

    def complete_transcription(self, message: str = "Vocal transcription completed"):
        self.update_stage(ProcessingStage.TRANSCRIPTION, 100, message)

    def start_chords(self, message: str = "Starting chord detection"):
        self.update_stage(ProcessingStage.CHORDS, 0, message)

    def update_chords(self, progress: int, message: Optional[str] = None):
        self.update_stage(ProcessingStage.CHORDS, progress, message)

    def complete_chords(self, message: str = "Chord detection completed"):
        self.update_stage(ProcessingStage.CHORDS, 100, message)
    
    def complete_job(self, message: str = "Processing completed successfully"):
        job = JobManager.update_job_status(self.db, self.job_id, JobStatus.COMPLETED)
        job.message = message
        self.db.commit()
        logger.info(f"Job {self.job_id} completed successfully")
    
    def fail_job(self, error_message: str):
        JobManager.update_job_status(
            self.db,
            self.job_id,
            JobStatus.FAILED,
            error_message
        )
        logger.error(f"Job {self.job_id} failed: {error_message}")
    
    def create_callback(self, stage: ProcessingStage) -> Callable[[int], None]:
        def callback(progress: int):
            self.update_stage(stage, progress)
        return callback

