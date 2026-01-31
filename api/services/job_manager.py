import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from api.database.models import Job, JobStatus, ProcessingStage
from api.utils.exceptions import JobNotFoundException, TooManyJobsException
from api.utils.logging import get_logger
from api.config import settings

logger = get_logger("job_manager")


class JobManager:
    
    @staticmethod
    def create_job(
        db: Session,
        input_filename: str,
        file_size: int
    ) -> Job:
        active_jobs = JobManager.count_active_jobs(db)
        if active_jobs >= settings.max_concurrent_jobs:
            raise TooManyJobsException(settings.max_concurrent_jobs)
        
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            input_filename=input_filename,
            file_size=file_size,
            status=JobStatus.QUEUED,
            progress=0,
            created_at=datetime.utcnow()
        )
        
        db.add(job)
        db.commit()
        db.refresh(job)
        
        logger.info(f"Created job {job_id} for file {input_filename}")
        return job
    
    @staticmethod
    def get_job(db: Session, job_id: str) -> Job:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise JobNotFoundException(job_id)
        return job
    
    @staticmethod
    def get_all_jobs(
        db: Session,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Job]:
        query = db.query(Job)
        
        if status:
            query = query.filter(Job.status == status)
        
        query = query.order_by(Job.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        return query.all()
    
    @staticmethod
    def update_job_status(
        db: Session,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None
    ) -> Job:
        job = JobManager.get_job(db, job_id)
        job.status = status
        
        if status == JobStatus.PROCESSING and not job.started_at:
            job.started_at = datetime.utcnow()
        
        if status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            job.completed_at = datetime.utcnow()
            job.progress = 100 if status == JobStatus.COMPLETED else job.progress
        
        if error_message:
            job.error_message = error_message
        
        db.commit()
        db.refresh(job)
        
        logger.info(f"Job {job_id} status updated to {status}")
        return job
    
    @staticmethod
    def update_job_stage(
        db: Session,
        job_id: str,
        stage: ProcessingStage,
        progress: int
    ) -> Job:
        job = JobManager.get_job(db, job_id)
        job.stage = stage
        job.progress = progress
        
        db.commit()
        db.refresh(job)
        
        logger.debug(f"Job {job_id} stage: {stage}, progress: {progress}%")
        return job
    
    @staticmethod
    def update_job_metadata(
        db: Session,
        job_id: str,
        duration: Optional[float] = None,
        tempo_bpm: Optional[float] = None,
        num_frames: Optional[int] = None,
        num_chords: Optional[int] = None
    ) -> Job:
        job = JobManager.get_job(db, job_id)

        if duration is not None:
            job.duration = duration
        if tempo_bpm is not None:
            job.tempo_bpm = tempo_bpm
        if num_frames is not None:
            job.num_frames = num_frames
        if num_chords is not None:
            job.num_chords = num_chords

        db.commit()
        db.refresh(job)

        logger.debug(f"Job {job_id} metadata updated")
        return job

    @staticmethod
    def update_file_paths(
        db: Session,
        job_id: str,
        input_file_path: Optional[str] = None,
        original_mp3_path: Optional[str] = None,
        stem_paths: Optional[dict] = None,
        frames_json_path: Optional[str] = None,
        chords_json_path: Optional[str] = None
    ) -> Job:
        job = JobManager.get_job(db, job_id)

        if input_file_path is not None:
            job.input_file_path = str(input_file_path)
        if original_mp3_path is not None:
            job.original_mp3_path = str(original_mp3_path)
        if stem_paths is not None:
            job.stem_paths = {k: str(v) for k, v in stem_paths.items()}
        if frames_json_path is not None:
            job.frames_json_path = str(frames_json_path)
        if chords_json_path is not None:
            job.chords_json_path = str(chords_json_path)

        db.commit()
        db.refresh(job)

        logger.debug(f"Job {job_id} file paths updated")
        return job

    @staticmethod
    def delete_job(db: Session, job_id: str) -> bool:
        job = JobManager.get_job(db, job_id)
        db.delete(job)
        db.commit()
        
        logger.info(f"Job {job_id} deleted")
        return True
    
    @staticmethod
    def count_active_jobs(db: Session) -> int:
        return db.query(Job).filter(
            or_(
                Job.status == JobStatus.QUEUED,
                Job.status == JobStatus.PROCESSING
            )
        ).count()
    
    @staticmethod
    def cleanup_old_jobs(db: Session, days: int = None) -> int:
        if days is None:
            days = settings.job_retention_days
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        old_jobs = db.query(Job).filter(
            and_(
                Job.completed_at < cutoff_date,
                or_(
                    Job.status == JobStatus.COMPLETED,
                    Job.status == JobStatus.FAILED
                )
            )
        ).all()
        
        count = len(old_jobs)
        for job in old_jobs:
            db.delete(job)
        
        db.commit()
        logger.info(f"Cleaned up {count} old jobs")
        return count

