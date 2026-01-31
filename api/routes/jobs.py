import json
import shutil
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from api.database.session import get_db
from api.database.models import JobStatus, Job
from api.models.schemas import (
    JobResponse,
    JobListResponse,
    JobStatusResponse,
    JobResultsResponse,
    StemInfo,
    StemsListResponse,
    DeleteJobResponse,
    FramesResponse,
    ChordsResponse,
    ProcessedFrame,
    Chord
)
from api.services.job_manager import JobManager
from api.utils.exceptions import JobNotFoundException
from api.utils.logging import get_logger
from api.config import settings

logger = get_logger("jobs_routes")

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip"),
    db: Session = Depends(get_db)
):
    jobs = JobManager.get_all_jobs(db, status=status, limit=limit, offset=offset)
    total = db.query(Job).count() if not status else db.query(Job).filter_by(status=status).count()

    return JobListResponse(
        jobs=[JobResponse.model_validate(job) for job in jobs],
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    job = JobManager.get_job(db, job_id)
    return JobResponse.model_validate(job)


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db)
):
    job = JobManager.get_job(db, job_id)
    return JobStatusResponse.model_validate(job)


@router.get("/{job_id}/results", response_model=JobResultsResponse)
async def get_job_results(
    job_id: str,
    db: Session = Depends(get_db)
):
    job = JobManager.get_job(db, job_id)
    job_storage_path = settings.get_job_storage_path(job_id)

    separated_dir = job_storage_path / "separated"
    transcription_dir = job_storage_path / "transcription"
    chords_dir = job_storage_path / "chords"

    stems = []
    if separated_dir.exists():
        for stem_file in separated_dir.glob("*.mp3"):
            stems.append(stem_file.stem.split("_")[-1])

    frames_available = (transcription_dir / f"{job_id}_processed_frames.json").exists()
    chords_available = (chords_dir / f"{job_id}_chords.json").exists()

    return JobResultsResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        input_filename=job.input_filename,
        duration=job.duration,
        tempo_bpm=job.tempo_bpm,
        stems=stems if stems else None,
        frames_available=frames_available,
        chords_available=chords_available,
        num_frames=job.num_frames,
        num_chords=job.num_chords,
        processing_time=job.processing_time if job.is_complete else None
    )


@router.get("/{job_id}/stems", response_model=StemsListResponse)
async def list_stems(
    job_id: str,
    db: Session = Depends(get_db)
):
    job = JobManager.get_job(db, job_id)
    job_storage_path = settings.get_job_storage_path(job_id)
    separated_dir = job_storage_path / "separated"

    if not separated_dir.exists():
        return StemsListResponse(job_id=job_id, stems=[])

    stems = []
    for stem_file in separated_dir.glob("*.mp3"):
        stem_name = stem_file.stem.split("_")[-1]
        stems.append(StemInfo(
            name=stem_name,
            filename=stem_file.name,
            size_bytes=stem_file.stat().st_size,
            download_url=f"/api/v1/jobs/{job_id}/stems/{stem_name}"
        ))

    return StemsListResponse(job_id=job_id, stems=stems)


@router.get("/{job_id}/stems/{stem_name}")
async def download_stem(
    job_id: str,
    stem_name: str,
    db: Session = Depends(get_db)
):
    job = JobManager.get_job(db, job_id)
    job_storage_path = settings.get_job_storage_path(job_id)
    separated_dir = job_storage_path / "separated"

    stem_files = list(separated_dir.glob(f"*_{stem_name}.mp3"))

    if not stem_files:
        raise JobNotFoundException(f"Stem '{stem_name}' not found for job {job_id}")

    stem_file = stem_files[0]

    return FileResponse(
        path=stem_file,
        media_type="audio/mpeg",
        filename=stem_file.name
    )



@router.get("/{job_id}/frames", response_model=FramesResponse)
async def get_processed_frames(
    job_id: str,
    db: Session = Depends(get_db)
):
    job = JobManager.get_job(db, job_id)
    job_storage_path = settings.get_job_storage_path(job_id)
    frames_file = job_storage_path / "transcription" / f"{job_id}_processed_frames.json"

    if not frames_file.exists():
        raise JobNotFoundException(f"Processed frames not found for job {job_id}")

    with open(frames_file, 'r') as f:
        data = json.load(f)

    frames = [ProcessedFrame(**frame) for frame in data.get("processed_frames", [])]

    return FramesResponse(
        job_id=job_id,
        metadata=data.get("metadata", {}),
        processed_frames=frames,
        frame_count=data.get("frame_count", len(frames))
    )


@router.get("/{job_id}/chords", response_model=ChordsResponse)
async def get_chords(
    job_id: str,
    db: Session = Depends(get_db)
):
    job = JobManager.get_job(db, job_id)
    job_storage_path = settings.get_job_storage_path(job_id)
    chords_file = job_storage_path / "chords" / f"{job_id}_chords.json"

    if not chords_file.exists():
        raise JobNotFoundException(f"Chords not found for job {job_id}")

    with open(chords_file, 'r') as f:
        data = json.load(f)

    chords = [Chord(**chord) for chord in data.get("chords", [])]

    return ChordsResponse(
        job_id=job_id,
        chords=chords,
        duration=data.get("duration", 0.0),
        sample_rate=data.get("sample_rate"),
        tempo_bpm=data.get("tempo_bpm"),
        key_info=data.get("key_info"),
        num_chords=len(chords)
    )


@router.delete("/{job_id}", response_model=DeleteJobResponse)
async def delete_job(
    job_id: str,
    db: Session = Depends(get_db)
):
    job = JobManager.get_job(db, job_id)

    job_storage_path = settings.get_job_storage_path(job_id)
    if job_storage_path.exists():
        shutil.rmtree(job_storage_path)
        logger.info(f"Deleted storage for job {job_id}")

    JobManager.delete_job(db, job_id)

    return DeleteJobResponse(
        job_id=job_id,
        message="Job and associated files deleted successfully",
        deleted=True
    )
