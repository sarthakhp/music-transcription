"""Publish completed jobs to Firebase Storage for the hosted viewer.

The local processing backend does the heavy work (download, separation,
transcription) and then uploads the finished artifacts here. The hosted,
read-only viewer reads them straight from Firebase Storage's public download
URLs — no always-on server required.

Bucket layout:
    index.json                       # lightweight list of all published jobs
    jobs/<id>/manifest.json          # per-job metadata + file URLs
    jobs/<id>/frames.json
    jobs/<id>/chords.json
    jobs/<id>/instruments.json
    jobs/<id>/original.mp3
    jobs/<id>/<stem>.mp3

Publishing is a no-op (with a warning) when Firebase isn't configured, so
local-only runs are unaffected.
"""

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from sqlalchemy.orm import Session

from api.config import settings
from api.database.models import Job, JobStatus
from api.services.job_manager import JobManager
from api.utils.logging import get_logger

logger = get_logger("storage_publisher")

_init_lock = threading.Lock()
_index_lock = threading.Lock()
_initialized = False

INDEX_PATH = "index.json"


def is_configured() -> bool:
    return settings.publish_enabled


def _get_bucket():
    """Initialise the Firebase app once and return the storage bucket."""
    global _initialized
    import firebase_admin
    from firebase_admin import credentials, storage

    with _init_lock:
        if not _initialized:
            cred = credentials.Certificate(str(settings.firebase_credentials_path))
            firebase_admin.initialize_app(
                cred, {"storageBucket": settings.firebase_storage_bucket}
            )
            _initialized = True
            logger.info(
                f"Firebase initialised (bucket={settings.firebase_storage_bucket})"
            )

    return storage.bucket()


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "application/json"
    if suffix == ".mp3":
        return "audio/mpeg"
    return "application/octet-stream"


def _download_url(bucket_name: str, object_path: str, token: str) -> str:
    """Build a stable Firebase Storage download URL (works on the free plan)."""
    encoded = quote(object_path, safe="")
    return (
        f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{encoded}"
        f"?alt=media&token={token}"
    )


def _upload_file(bucket, object_path: str, local_path: Path) -> str:
    """Upload a local file and return a stable public download URL."""
    token = str(uuid.uuid4())
    blob = bucket.blob(object_path)
    blob.metadata = {"firebaseStorageDownloadTokens": token}
    blob.upload_from_filename(str(local_path), content_type=_content_type(local_path))
    return _download_url(bucket.name, object_path, token)


def _upload_json(bucket, object_path: str, data: dict) -> str:
    token = str(uuid.uuid4())
    blob = bucket.blob(object_path)
    blob.metadata = {"firebaseStorageDownloadTokens": token}
    blob.upload_from_string(
        json.dumps(data, ensure_ascii=False), content_type="application/json"
    )
    return _download_url(bucket.name, object_path, token)


def _collect_artifacts(job: Job) -> dict[str, Path]:
    """Map artifact key -> local file path, skipping anything missing on disk.

    File locations mirror the read paths in api/routes/jobs.py.
    """
    storage_path = settings.get_job_storage_path(job.id)
    artifacts: dict[str, Path] = {}

    candidates = {
        "frames": storage_path / "transcription" / f"{job.id}_processed_frames.json",
        "chords": storage_path / "chords" / f"{job.id}_chords.json",
        "instruments": storage_path / "instruments" / f"{job.id}_instruments.json",
    }
    for key, path in candidates.items():
        if path.exists():
            artifacts[key] = path

    # Original audio: prefer the recorded path, else look in separated/.
    if job.original_mp3_path and Path(job.original_mp3_path).exists():
        artifacts["original"] = Path(job.original_mp3_path)

    # Stems: prefer the recorded mapping, else glob the separated dir.
    stem_paths: dict[str, Path] = {}
    if job.stem_paths:
        for name, p in job.stem_paths.items():
            if p and Path(p).exists():
                stem_paths[name] = Path(p)
    else:
        separated = storage_path / "separated"
        if separated.exists():
            for mp3 in separated.glob("*.mp3"):
                stem_paths[mp3.stem.split("_")[-1]] = mp3

    for name, p in stem_paths.items():
        artifacts[f"stem:{name}"] = p

    return artifacts


def _viewer_instruments(raw: dict, job_id: str) -> dict:
    """Reshape the stored instruments JSON ({metadata, tracks}) into the shape
    the viewer parses ({job_id, duration, total_notes, tempo_bpm, tracks}),
    matching the /instruments API endpoint."""
    metadata = raw.get("metadata", {})
    tracks = {}
    for name, track in raw.get("tracks", {}).items():
        tracks[name] = {
            "instrument": name,
            "num_notes": track.get("num_notes", len(track.get("notes", []))),
            "duration": track.get("duration", 0.0),
            "notes": track.get("notes", []),
        }
    return {
        "job_id": job_id,
        "tracks": tracks,
        "duration": metadata.get("duration", 0.0),
        "total_notes": metadata.get("total_notes", 0),
        "tempo_bpm": metadata.get("tempo_bpm", 0.0),
    }


def publish_job(db: Session, job_id: str) -> dict:
    """Upload a completed job's artifacts to Firebase Storage and refresh the
    index. Returns the manifest. Raises if Firebase isn't configured."""
    if not is_configured():
        raise RuntimeError(
            "Remote publishing is not configured. Set firebase_credentials_path "
            "and firebase_storage_bucket."
        )

    job = JobManager.get_job(db, job_id)
    if job.status != JobStatus.COMPLETED:
        raise ValueError(f"Job {job_id} is not completed (status={job.status.value})")

    bucket = _get_bucket()
    artifacts = _collect_artifacts(job)

    def upload(item: tuple[str, Path]) -> tuple[str, str]:
        key, path = item
        if key.startswith("stem:"):
            stem_name = key.split(":", 1)[1]
            return key, _upload_file(bucket, f"jobs/{job_id}/{stem_name}.mp3", path)
        if key == "instruments":
            # Reshape to the viewer's expected shape so the Flutter parser
            # works unchanged (mirrors the /instruments endpoint transform).
            data = _viewer_instruments(json.loads(path.read_text()), job_id)
            return key, _upload_json(bucket, f"jobs/{job_id}/instruments.json", data)
        # frames.json / chords.json are already in the shape the viewer
        # parses; upload them verbatim.
        return key, _upload_file(bucket, f"jobs/{job_id}/{key}{path.suffix}", path)

    # The files are independent, and a job is several MB of audio, so upload
    # them in parallel: a serial upload can outlast the app's shutdown grace
    # period and get killed half-way.
    files: dict = {"stems": {}}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for key, url in pool.map(upload, artifacts.items()):
            if key.startswith("stem:"):
                files["stems"][key.split(":", 1)[1]] = url
            else:
                files[key] = url

    manifest = {
        "id": job.id,
        "title": job.video_title or job.input_filename,
        "input_filename": job.input_filename,
        "source_type": job.source_type,
        "source_url": job.source_url,
        "separation_model": job.separation_model,
        "audio_type": job.audio_type,
        "display_name": job.display_name,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "duration": job.duration,
        "tempo_bpm": job.tempo_bpm,
        "num_frames": job.num_frames,
        "num_chords": job.num_chords,
        "stems": sorted(files["stems"].keys()),
        "files": files,
    }
    manifest_url = _upload_json(bucket, f"jobs/{job_id}/manifest.json", manifest)
    manifest["manifest_url"] = manifest_url

    _update_index(bucket, manifest)

    logger.info(f"Published job {job_id} to Firebase Storage")
    return manifest


def _update_index(bucket, manifest: dict) -> None:
    """Read-modify-write the bucket-level index of published jobs."""
    summary = {
        "id": manifest["id"],
        "title": manifest["title"],
        "source_type": manifest["source_type"],
        "created_at": manifest["created_at"],
        "duration": manifest["duration"],
        "tempo_bpm": manifest["tempo_bpm"],
        "num_chords": manifest["num_chords"],
        "manifest_url": manifest["manifest_url"],
        "audio_type": manifest.get("audio_type") or "mixed",
        "display_name": manifest.get("display_name"),
    }

    with _index_lock:
        # get_blob loads the object's metadata (bucket.blob + exists() does
        # not), which carries the download token the hosted viewer's index
        # URL depends on.
        existing = bucket.get_blob(INDEX_PATH)
        blob = existing or bucket.blob(INDEX_PATH)
        index: dict = {"jobs": []}
        if existing:
            try:
                index = json.loads(blob.download_as_text())
            except (ValueError, UnicodeDecodeError):
                logger.warning("index.json was unreadable — rebuilding it")
                index = {"jobs": []}

        jobs = [j for j in index.get("jobs", []) if j.get("id") != manifest["id"]]
        jobs.append(summary)
        # Sort by created_at descending so the index stays newest-first
        # regardless of publish order (backfills publish newest-first,
        # retries can complete out of order, etc).
        jobs.sort(key=lambda j: j.get("created_at") or "", reverse=True)
        index["jobs"] = jobs
        index["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Preserve the download token so the index URL stays stable across writes.
        token = (existing.metadata or {}).get("firebaseStorageDownloadTokens") if existing else None
        token = token or str(uuid.uuid4())
        blob.metadata = {"firebaseStorageDownloadTokens": token}
        blob.upload_from_string(
            json.dumps(index, ensure_ascii=False), content_type="application/json"
        )


def sync_job_metadata(job: Job) -> bool:
    """Push a job's editable metadata (display name, audio type) to its
    already-published manifest and index entry, without re-uploading any
    media. Returns False if the job isn't published or cloud isn't set up."""
    if not is_configured():
        return False
    bucket = _get_bucket()
    object_path = f"jobs/{job.id}/manifest.json"
    blob = bucket.get_blob(object_path)
    if blob is None:
        return False

    manifest = json.loads(blob.download_as_text())
    manifest["display_name"] = job.display_name
    manifest["audio_type"] = job.audio_type

    # Rewrite in place under the same token so existing URLs stay valid.
    token = (blob.metadata or {}).get("firebaseStorageDownloadTokens") or str(uuid.uuid4())
    blob.metadata = {"firebaseStorageDownloadTokens": token}
    blob.upload_from_string(
        json.dumps(manifest, ensure_ascii=False), content_type="application/json"
    )
    manifest["manifest_url"] = _download_url(bucket.name, object_path, token)
    _update_index(bucket, manifest)
    return True


def try_sync_job_metadata(job_id: str) -> None:
    """Best-effort metadata sync for a background task; never raises."""
    from api.database.session import SessionLocal

    db = SessionLocal()
    try:
        sync_job_metadata(JobManager.get_job(db, job_id))
    except Exception as e:
        logger.warning(f"Could not sync metadata for job {job_id}: {e}")
    finally:
        db.close()


_sync_lock = threading.Lock()

# A job that completed very recently may still be publishing in its own
# pipeline process; leave those alone unless the caller forces a sync.
_RECENT_JOB_GRACE = timedelta(minutes=5)


def publish_missing_jobs(force: bool = False) -> list[str]:
    """Publish every completed local job that is absent from the cloud index.

    Self-heals publishes that never finished (the app quit mid-upload, the
    network dropped, ...). Best-effort per job: one failure doesn't stop the
    rest. Returns the ids that were published.
    """
    if not (is_configured() and settings.publish_on_complete):
        return []
    if not _sync_lock.acquire(blocking=False):
        return []  # a sync is already running
    from api.database.session import SessionLocal

    published: list[str] = []
    db = SessionLocal()
    try:
        bucket = _get_bucket()
        index_blob = bucket.get_blob(INDEX_PATH)
        in_cloud = (
            {j.get("id") for j in json.loads(index_blob.download_as_text()).get("jobs", [])}
            if index_blob
            else set()
        )
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - _RECENT_JOB_GRACE
        for job in db.query(Job).filter(Job.status == JobStatus.COMPLETED).all():
            if job.id in in_cloud:
                continue
            if not force and job.completed_at and job.completed_at > cutoff:
                continue
            try:
                publish_job(db, job.id)
                published.append(job.id)
            except Exception as e:
                logger.error(f"Resync could not publish job {job.id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Cloud resync failed: {e}", exc_info=True)
    finally:
        db.close()
        _sync_lock.release()
    if published:
        logger.info(f"Resync published {len(published)} job(s): {published}")
    return published


def try_publish_job(db: Session, job_id: str) -> Optional[dict]:
    """Best-effort publish used by the pipeline. Never raises — a publish
    failure must not fail an otherwise-successful transcription job."""
    if not (is_configured() and settings.publish_on_complete):
        if not is_configured():
            logger.info("Remote publishing not configured — skipping publish")
        return None
    try:
        return publish_job(db, job_id)
    except Exception as e:
        logger.error(f"Failed to publish job {job_id}: {e}", exc_info=True)
        return None
