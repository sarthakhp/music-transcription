"""Browse and import jobs published to Firebase Storage.

The bundled app only knows about jobs it processed itself. This lets it also
list everything in the published index, and pull a cloud-only job down into
local storage on demand. An imported job is an ordinary local job (same id,
same on-disk layout the pipeline writes), so every existing endpoint serves it
without knowing where it came from.

Reads only: this module never writes to the bucket.
"""

import json
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from api.config import settings
from api.database.models import Job, JobStatus
from api.services import storage_publisher
from api.utils.exceptions import JobNotFoundException
from api.utils.logging import get_logger

logger = get_logger("cloud_library")

_INDEX_TTL_SECONDS = 30
_cache_lock = threading.Lock()
_cached: tuple[float, list[dict]] | None = None
_import_lock = threading.Lock()


def is_configured() -> bool:
    return storage_publisher.is_configured()


def list_cloud_jobs(force: bool = False) -> list[dict]:
    """Published job summaries (newest first), cached briefly. Raises if
    Firebase is configured but unreachable."""
    global _cached
    if not is_configured():
        return []
    with _cache_lock:
        if not force and _cached and time.monotonic() - _cached[0] < _INDEX_TTL_SECONDS:
            return _cached[1]
        bucket = storage_publisher._get_bucket()
        blob = bucket.blob(storage_publisher.INDEX_PATH)
        jobs: list[dict] = []
        if blob.exists():
            jobs = json.loads(blob.download_as_text()).get("jobs", [])
        _cached = (time.monotonic(), jobs)
        return jobs


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _local_instruments(viewer_shaped: dict) -> dict:
    """Inverse of storage_publisher._viewer_instruments: back to the
    {metadata, tracks} layout the local /instruments endpoint reads."""
    return {
        "metadata": {
            "duration": viewer_shaped.get("duration", 0.0),
            "total_notes": viewer_shaped.get("total_notes", 0),
            "tempo_bpm": viewer_shaped.get("tempo_bpm", 0.0),
        },
        "tracks": viewer_shaped.get("tracks", {}),
    }


def import_cloud_job(db: Session, job_id: str) -> Job:
    """Download a published job into local storage and register it. A no-op
    that returns the existing job if it is already present locally."""
    with _import_lock:
        existing = db.query(Job).filter(Job.id == job_id).first()
        if existing:
            return existing
        if not is_configured():
            raise JobNotFoundException(job_id)

        bucket = storage_publisher._get_bucket()
        manifest_blob = bucket.blob(f"jobs/{job_id}/manifest.json")
        if not manifest_blob.exists():
            raise JobNotFoundException(job_id)
        manifest = json.loads(manifest_blob.download_as_text())
        files = manifest.get("files", {})

        job_dir = settings.get_job_storage_path(job_id)
        try:
            paths = _download_artifacts(bucket, job_id, job_dir, files)
            job = _register_job(db, job_id, manifest, paths)
        except Exception:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise
        logger.info(f"Imported cloud job {job_id} ({manifest.get('title')!r})")
        return job


def _download_artifacts(bucket, job_id: str, job_dir: Path, files: dict) -> dict:
    """Fetch every published file into the layout the pipeline would have
    written. Returns the paths to record on the Job row."""
    paths: dict = {"stems": {}}

    def fetch(object_name: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        bucket.blob(f"jobs/{job_id}/{object_name}").download_to_filename(str(dest))
        return dest

    if files.get("frames"):
        paths["frames"] = fetch(
            "frames.json", job_dir / "transcription" / f"{job_id}_processed_frames.json"
        )
    if files.get("chords"):
        paths["chords"] = fetch("chords.json", job_dir / "chords" / f"{job_id}_chords.json")
    if files.get("instruments"):
        dest = job_dir / "instruments" / f"{job_id}_instruments.json"
        fetch("instruments.json", dest)
        dest.write_text(json.dumps(_local_instruments(json.loads(dest.read_text()))))
        paths["instruments"] = dest

    separated = job_dir / "separated"
    if files.get("original"):
        paths["original"] = fetch("original.mp3", separated / f"{job_id}_original.mp3")
    for stem in files.get("stems", {}):
        if stem == "original":
            continue
        paths["stems"][stem] = fetch(f"{stem}.mp3", separated / f"{job_id}_{stem}.mp3")
    return paths


def _register_job(db: Session, job_id: str, manifest: dict, paths: dict) -> Job:
    filename = manifest.get("input_filename") or manifest.get("title") or "Untitled"
    # The manifest title is the video title when there is one, else the filename.
    title = manifest.get("title")
    video_title = title if title and title != filename else None
    job = Job(
        id=job_id,
        status=JobStatus.COMPLETED,
        progress=100,
        stage_progress=100,
        created_at=_parse_time(manifest.get("created_at")) or datetime.utcnow(),
        completed_at=_parse_time(manifest.get("completed_at")),
        source_type=manifest.get("source_type") or "file",
        source_url=manifest.get("source_url"),
        video_title=video_title,
        separation_model=manifest.get("separation_model"),
        audio_type=manifest.get("audio_type") or "mixed",
        display_name=manifest.get("display_name"),
        input_filename=filename,
        file_size=0,
        duration=manifest.get("duration"),
        tempo_bpm=manifest.get("tempo_bpm"),
        num_frames=manifest.get("num_frames"),
        num_chords=manifest.get("num_chords"),
        original_mp3_path=str(paths["original"]) if "original" in paths else None,
        stem_paths={k: str(v) for k, v in paths["stems"].items()},
        frames_json_path=str(paths["frames"]) if "frames" in paths else None,
        instruments_json_path=str(paths["instruments"]) if "instruments" in paths else None,
        chords_json_path=str(paths["chords"]) if "chords" in paths else None,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
