from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from api.database.session import get_db
from api.models.schemas import TranscribeResponse, URLMetadataResponse
from api.services.job_manager import JobManager
from api.services.youtube_downloader import (
    fetch_metadata,
    UnsupportedURLError,
    VideoDurationError,
    MAX_DURATION_SECONDS,
)
from api.workers.task_queue import task_queue
from api.utils.exceptions import TooManyJobsException
from api.utils.logging import get_logger
from api.config import settings

logger = get_logger("url_transcription_routes")

router = APIRouter(prefix="/api/v1", tags=["url-transcription"])


class TranscribeURLRequest(BaseModel):
    url: str
    start_time: float | None = None
    end_time: float | None = None
    separation_model: str | None = None

    @field_validator("url")
    @classmethod
    def url_must_be_non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("url must not be empty")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("url must start with http:// or https://")
        return v


@router.get("/url/metadata", response_model=URLMetadataResponse)
async def get_url_metadata(url: str):
    """Fetch video metadata without creating a job or downloading anything.

    Used by the UI to show a preview panel (thumbnail, title, duration) so
    the user can set trim handles before submitting.

    No duration limit is enforced here — the user may want to trim a long
    video down to an acceptable section.
    """
    logger.info(f"Metadata request for URL: {url}")

    if not url.strip():
        raise HTTPException(status_code=422, detail="url parameter is required")

    try:
        metadata = fetch_metadata(url.strip(), check_duration=False)
    except UnsupportedURLError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return URLMetadataResponse(
        title=metadata.title,
        duration=metadata.duration,
        uploader=metadata.uploader,
        thumbnail=metadata.thumbnail,
        url=url,
        max_duration_seconds=MAX_DURATION_SECONDS,
    )


@router.post(
    "/transcribe/url",
    response_model=TranscribeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def transcribe_url(
    request: TranscribeURLRequest,
    db: Session = Depends(get_db),
):
    logger.info(f"Received URL transcription request: {request.url}")

    from src.source_separation import DEFAULT_MODEL_KEY, get_model
    model_key = request.separation_model or DEFAULT_MODEL_KEY
    try:
        get_model(model_key)
    except KeyError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not task_queue.can_accept_job():
        raise TooManyJobsException(settings.max_concurrent_jobs)

    # Fast metadata fetch — no download, just API call to get title/duration.
    # check_duration=False: validate the trimmed selection instead (below).
    try:
        metadata = fetch_metadata(request.url, check_duration=False)
    except UnsupportedURLError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Validate that the selected section (after trimming) is within the limit.
    effective_start = request.start_time or 0.0
    effective_end = request.end_time or metadata.duration
    selected_duration = effective_end - effective_start

    if selected_duration <= 0:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")

    if selected_duration > MAX_DURATION_SECONDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Selected section is {selected_duration:.0f}s — "
                f"maximum is {MAX_DURATION_SECONDS}s ({MAX_DURATION_SECONDS // 60} minutes). "
                f"Use the trim handles to select a shorter section."
            ),
        )

    logger.info(
        f"Video metadata: title={metadata.title!r}, "
        f"duration={metadata.duration:.0f}s, uploader={metadata.uploader!r}"
    )

    # Safe filename derived from video title
    safe_title = "".join(
        c if c.isalnum() or c in " -_." else "_" for c in metadata.title
    )[:128].strip() or "audio"

    job = JobManager.create_job(
        db=db,
        input_filename=f"{safe_title}.mp3",
        file_size=0,
        source_type="url",
        source_url=request.url,
        video_title=metadata.title,
        separation_model=model_key,
    )

    # Submit to pipeline subprocess — download happens as Stage 0
    from api.routes.transcription import run_pipeline_task
    from api.middleware.context import get_trace_id

    await task_queue.submit_job(
        job.id,
        run_pipeline_task,
        job.id,
        None,
        trace_id=get_trace_id(),
        source_url=request.url,
        start_time=request.start_time,
        end_time=request.end_time,
        separation_model=model_key,
    )

    logger.info(f"URL job {job.id} submitted: {metadata.title!r}")

    return TranscribeResponse(
        job_id=job.id,
        status=job.status,
        message=f"Job created successfully. Downloading: {metadata.title}",
    )
