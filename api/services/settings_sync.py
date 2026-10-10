"""Per-song viewer settings stored in cloud storage.

One small JSON object per song at settings/<job_id>.json. The object gets a
download token derived from the job id, so the hosted (read-only) viewer can
build its public URL from the id alone, with no manifest or index rewrite
each time a setting changes.
"""

import json
import uuid

from api.services import storage_publisher

MAX_SETTINGS_BYTES = 32 * 1024


def _object_path(job_id: str) -> str:
    return f"settings/{job_id}.json"


def _token(job_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"music-transcription-settings:{job_id}"))


def is_configured() -> bool:
    return storage_publisher.is_configured()


def read_settings(job_id: str) -> dict | None:
    """The stored settings, or None if there are none (or no cloud)."""
    if not is_configured():
        return None
    blob = storage_publisher._get_bucket().blob(_object_path(job_id))
    if not blob.exists():
        return None
    return json.loads(blob.download_as_text())


def write_settings(job_id: str, settings: dict) -> bool:
    """Store settings for a song. Returns False when there is no cloud."""
    if not is_configured():
        return False
    payload = json.dumps(settings, ensure_ascii=False)
    if len(payload.encode()) > MAX_SETTINGS_BYTES:
        raise ValueError("settings too large")
    blob = storage_publisher._get_bucket().blob(_object_path(job_id))
    blob.metadata = {"firebaseStorageDownloadTokens": _token(job_id)}
    blob.cache_control = "no-cache"
    blob.upload_from_string(payload, content_type="application/json")
    return True
