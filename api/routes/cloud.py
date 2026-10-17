from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from api.database.models import Job
from api.database.session import get_db
from api.models.schemas import JobResponse
from api.services import cloud_library, settings_sync
from api.services.job_manager import JobManager
from api.utils.logging import get_logger

logger = get_logger("cloud_routes")

router = APIRouter(prefix="/api/v1/cloud", tags=["cloud"])


@router.get("/jobs")
def list_cloud_jobs(db: Session = Depends(get_db)):
    """Jobs published to cloud storage, each flagged with whether it is
    already stored on this device. `configured` is false when this install
    has no cloud storage, so the UI can skip the cloud badges entirely."""
    if not cloud_library.is_configured():
        return {"configured": False, "available": False, "jobs": []}
    try:
        published = cloud_library.list_cloud_jobs()
    except Exception as e:
        logger.warning(f"Cloud index unavailable: {e}")
        return {"configured": True, "available": False, "jobs": []}

    local_ids = {row[0] for row in db.query(Job.id).all()}
    jobs = [{**j, "on_device": j.get("id") in local_ids} for j in published]
    return {"configured": True, "available": True, "jobs": jobs}


@router.post("/jobs/{job_id}/import", response_model=JobResponse)
def import_cloud_job(job_id: str, db: Session = Depends(get_db)):
    """Download a cloud-only job onto this device. Safe to call for a job
    that is already local."""
    try:
        return cloud_library.import_cloud_job(db, job_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Import of cloud job {job_id} failed: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Could not download job: {e}")


@router.get("/jobs/{job_id}/settings")
def get_job_settings(job_id: str):
    """The song's viewer settings from the cloud (`settings` is null when
    none are stored or the cloud is unavailable; the app then keeps using its
    local copy)."""
    try:
        return {"settings": settings_sync.read_settings(job_id)}
    except Exception as e:
        logger.warning(f"Could not read settings for {job_id}: {e}")
        return {"settings": None}


@router.put("/jobs/{job_id}/settings")
async def put_job_settings(job_id: str, request: Request, db: Session = Depends(get_db)):
    """Store the song's viewer settings in the cloud."""
    JobManager.get_job(db, job_id)  # 404 for unknown songs
    body = await request.body()
    if len(body) > settings_sync.MAX_SETTINGS_BYTES:
        raise HTTPException(status_code=413, detail="Settings too large")
    try:
        data = await request.json()
        if not isinstance(data, dict):
            raise ValueError("expected an object")
    except ValueError:
        raise HTTPException(status_code=422, detail="Settings must be a JSON object")
    try:
        stored = await run_in_threadpool(settings_sync.write_settings, job_id, data)
    except Exception as e:
        logger.warning(f"Could not store settings for {job_id}: {e}")
        raise HTTPException(status_code=502, detail="Cloud storage unavailable")
    return {"stored": stored}


@router.post("/sync", status_code=202)
def sync_cloud(background_tasks: BackgroundTasks):
    """Publish any completed local jobs that are missing from the cloud. Runs
    in the background; the cloud list reflects the result shortly after."""
    from api.services.storage_publisher import publish_missing_jobs

    if not cloud_library.is_configured():
        return {"started": False}
    background_tasks.add_task(publish_missing_jobs, True)
    return {"started": True}
