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
from datetime import datetime, timezone
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

    files: dict = {"stems": {}}
    for key, path in artifacts.items():
        if key.startswith("stem:"):
            stem_name = key.split(":", 1)[1]
            object_path = f"jobs/{job_id}/{stem_name}.mp3"
            files["stems"][stem_name] = _upload_file(bucket, object_path, path)
        elif key == "instruments":
            # Reshape to the viewer's expected shape so the Flutter parser
            # works unchanged (mirrors the /instruments endpoint transform).
            data = _viewer_instruments(json.loads(path.read_text()), job_id)
            files[key] = _upload_json(bucket, f"jobs/{job_id}/instruments.json", data)
        else:
            # frames.json / chords.json are already in the shape the viewer
            # parses; upload them verbatim.
            ext = path.suffix
            object_path = f"jobs/{job_id}/{key}{ext}"
            files[key] = _upload_file(bucket, object_path, path)

    manifest = {
        "id": job.id,
        "title": job.video_title or job.input_filename,
        "input_filename": job.input_filename,
        "source_type": job.source_type,
        "source_url": job.source_url,
        "separation_model": job.separation_model,
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
    }

    with _index_lock:
        blob = bucket.blob(INDEX_PATH)
        index: dict = {"jobs": []}
        if blob.exists():
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
        token = (blob.metadata or {}).get("firebaseStorageDownloadTokens") if blob.exists() else None
        token = token or str(uuid.uuid4())
        blob.metadata = {"firebaseStorageDownloadTokens": token}
        blob.upload_from_string(
            json.dumps(index, ensure_ascii=False), content_type="application/json"
        )


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
