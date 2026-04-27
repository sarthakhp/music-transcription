import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config import settings
from api.database.session import init_db, close_db, SessionLocal
from api.database.models import JobStatus
from api.middleware.context import TraceIDMiddleware
from api.utils.logging import setup_logging, get_logger
from api.routes import transcription, jobs, url_transcription
from api.workers.task_queue import task_queue
from api.models.schemas import HealthResponse
from api.services.job_manager import JobManager
from src.audio_io import validate_ffmpeg
from src.source_separation.memory import clear_memory

logger = get_logger("main")

app = FastAPI(
    title="Music Transcription API",
    description="API for audio source separation, vocal transcription, and chord detection",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(TraceIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(transcription.router)
app.include_router(url_transcription.router)
app.include_router(jobs.router)


def _recover_orphaned_jobs():
    """Clean up after a previous crash (SIGKILL, power loss, etc.).

    1. Mark any QUEUED/PROCESSING jobs as FAILED so they don't block the queue.
    2. Remove orphaned temp files left behind by mid-flight separations.
    """
    db = SessionLocal()
    try:
        from api.database.models import Job

        stuck_jobs = db.query(Job).filter(
            Job.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING])
        ).all()

        if stuck_jobs:
            for job in stuck_jobs:
                logger.warning(
                    f"Recovering orphaned job {job.id} "
                    f"(was {job.status.value}, stage={job.stage})"
                )
                job.status = JobStatus.FAILED
                job.error_message = "Server was restarted while job was in progress"

            db.commit()
            logger.info(f"Recovered {len(stuck_jobs)} orphaned job(s)")

    finally:
        db.close()

    _cleanup_temp_files()


def _cleanup_temp_files():
    """Remove temp files left behind by crashed separations."""
    jobs_dir = settings.storage_path / "jobs"
    if not jobs_dir.exists():
        return

    patterns = [
        "*/separated/chunk_*.wav",
        "*/separated/_temp_*.wav",
    ]

    total_cleaned = 0
    for pattern in patterns:
        for temp_file in jobs_dir.glob(pattern):
            try:
                size_kb = temp_file.stat().st_size / 1024
                temp_file.unlink()
                total_cleaned += 1
                logger.info(f"Cleaned up orphaned temp file: {temp_file} ({size_kb:.0f}KB)")
            except OSError as e:
                logger.warning(f"Failed to remove temp file {temp_file}: {e}")

    if total_cleaned > 0:
        logger.info(f"Cleaned up {total_cleaned} orphaned temp file(s)")


@app.on_event("startup")
async def startup_event():
    setup_logging()
    logger.info("Starting Music Transcription API...")
    logger.info(f"Server: {settings.api_host}:{settings.api_port}")
    logger.info(f"Storage path: {settings.storage_path}")
    logger.info(f"Max file size: {settings.max_file_size_mb}MB")
    logger.info(f"Max concurrent jobs: {settings.max_concurrent_jobs}")

    init_db()
    logger.info("Database initialized")

    _recover_orphaned_jobs()

    # Validate FFmpeg is available before accepting requests
    validate_ffmpeg()

    # Note: the separation model is no longer preloaded in the main process.
    # Each job subprocess loads it from the cached file on disk (~2-3s).
    # This is required because spawn subprocesses don't inherit parent memory,
    # and MPS GPU state is not safe to fork.
    logger.info(
        "Separation model will be loaded per-job from disk cache "
        "(spawn subprocesses cannot inherit parent MPS/GPU state)"
    )

    logger.info("API startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Music Transcription API...")

    # Wait up to 30s for running jobs, then kill them
    task_queue.shutdown(wait=True, timeout=30)

    # Free any GPU/MPS memory held by the main process
    clear_memory("mps")
    clear_memory("cpu")
    logger.info("GPU/MPS memory cleared")

    # Dispose database connection pool
    close_db()

    # Flush and close all logging handlers so no buffered entries are lost
    for handler in logging.root.handlers:
        handler.flush()
        handler.close()


@app.get("/")
async def root():
    return {
        "message": "Music Transcription API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    queue_status = task_queue.get_queue_status()

    return HealthResponse(
        status="healthy",
        database="connected",
        storage=str(settings.storage_path),
        active_jobs=queue_status["active_jobs"],
        max_concurrent_jobs=queue_status["max_concurrent_jobs"]
    )
