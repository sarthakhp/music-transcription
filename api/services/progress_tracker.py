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
    
    def update_stage(self, stage: ProcessingStage, stage_progress: int = 0):
        start, end = self._stage_weights[stage]
        overall_progress = start + int((end - start) * (stage_progress / 100))
        overall_progress = min(max(overall_progress, 0), 100)
        
        JobManager.update_job_stage(
            self.db,
            self.job_id,
            stage,
            overall_progress
        )
        
        logger.info(f"Job {self.job_id}: {stage.value} - {stage_progress}% (overall: {overall_progress}%)")
    
    def start_separation(self):
        JobManager.update_job_status(self.db, self.job_id, JobStatus.PROCESSING)
        self.update_stage(ProcessingStage.SEPARATION, 0)
    
    def update_separation(self, progress: int):
        self.update_stage(ProcessingStage.SEPARATION, progress)
    
    def complete_separation(self):
        self.update_stage(ProcessingStage.SEPARATION, 100)
    
    def start_transcription(self):
        self.update_stage(ProcessingStage.TRANSCRIPTION, 0)
    
    def update_transcription(self, progress: int):
        self.update_stage(ProcessingStage.TRANSCRIPTION, progress)
    
    def complete_transcription(self):
        self.update_stage(ProcessingStage.TRANSCRIPTION, 100)
    
    def start_chords(self):
        self.update_stage(ProcessingStage.CHORDS, 0)
    
    def update_chords(self, progress: int):
        self.update_stage(ProcessingStage.CHORDS, progress)
    
    def complete_chords(self):
        self.update_stage(ProcessingStage.CHORDS, 100)
    
    def complete_job(self):
        JobManager.update_job_status(self.db, self.job_id, JobStatus.COMPLETED)
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

