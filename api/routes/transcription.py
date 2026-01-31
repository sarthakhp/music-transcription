import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.database.session import get_db
from api.models.schemas import TranscribeResponse
from api.services.job_manager import JobManager
from api.workers.task_queue import task_queue
from api.workers.pipeline_worker import PipelineWorker
from api.config import settings
from api.utils.exceptions import (
    FileTooLargeException,
    InvalidAudioFileException,
    TooManyJobsException
)
from api.utils.logging import get_logger

logger = get_logger("transcription_routes")

router = APIRouter(prefix="/api/v1", tags=["transcription"])

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".webm"}
ALLOWED_MIME_TYPES = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/flac",
    "audio/mp4",
    "audio/x-m4a",
    "audio/ogg",
    "audio/webm"
}


def validate_audio_file(file: UploadFile) -> None:
    if not file.filename:
        raise InvalidAudioFileException("No filename provided")
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise InvalidAudioFileException(
            f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        logger.warning(f"Unexpected MIME type: {file.content_type} for file {file.filename}")


async def save_upload_file(upload_file: UploadFile, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    file_size = 0
    with open(destination, "wb") as buffer:
        while chunk := await upload_file.read(8192):
            file_size += len(chunk)
            
            if file_size > settings.max_file_size_bytes:
                buffer.close()
                destination.unlink(missing_ok=True)
                raise FileTooLargeException(settings.max_file_size_mb)
            
            buffer.write(chunk)
    
    return file_size


def run_pipeline_task(job_id: str, input_audio_path: Path):
    from api.database.session import SessionLocal
    
    db = SessionLocal()
    try:
        worker = PipelineWorker(db, job_id)
        worker.run(input_audio_path)
    finally:
        db.close()


@router.post("/transcribe", response_model=TranscribeResponse, status_code=status.HTTP_202_ACCEPTED)
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file to transcribe"),
    db: Session = Depends(get_db)
):
    logger.info(f"Received transcription request for file: {file.filename}")
    
    validate_audio_file(file)
    
    if not task_queue.can_accept_job():
        raise TooManyJobsException(settings.max_concurrent_jobs)
    
    job = JobManager.create_job(
        db=db,
        input_filename=file.filename,
        file_size=0
    )
    
    job_storage_path = settings.get_job_storage_path(job.id)
    input_dir = job_storage_path / "input"
    input_file_path = input_dir / file.filename
    
    try:
        file_size = await save_upload_file(file, input_file_path)

        JobManager.update_job_metadata(db, job.id, duration=None)
        job.file_size = file_size
        db.commit()

        JobManager.update_file_paths(db, job.id, input_file_path=str(input_file_path))

        logger.info(f"File saved: {input_file_path} ({file_size} bytes)")

        await task_queue.submit_job(
            job.id,
            run_pipeline_task,
            job.id,
            input_file_path
        )
        
        logger.info(f"Job {job.id} submitted to task queue")
        
        return TranscribeResponse(
            job_id=job.id,
            status=job.status,
            message=f"Job created successfully. Processing started."
        )
        
    except Exception as e:
        logger.error(f"Failed to process upload for job {job.id}: {str(e)}")
        JobManager.delete_job(db, job.id)
        
        if input_file_path.exists():
            input_file_path.unlink()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process upload: {str(e)}"
        )


@router.get("/queue/status")
async def get_queue_status():
    return task_queue.get_queue_status()

