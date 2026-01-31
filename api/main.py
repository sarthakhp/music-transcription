from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config import settings
from api.database.session import init_db
from api.utils.logging import setup_logging, get_logger
from api.routes import transcription, jobs
from api.workers.task_queue import task_queue
from api.models.schemas import HealthResponse

logger = get_logger("main")

app = FastAPI(
    title="Music Transcription API",
    description="API for audio source separation, vocal transcription, and chord detection",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transcription.router)
app.include_router(jobs.router)


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
    
    logger.info("API startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Music Transcription API...")
    task_queue.shutdown(wait=True)
    logger.info("Task queue shutdown complete")


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

