#!/usr/bin/env python3
"""
Debug CLI — run a pipeline job directly without the full app stack.

Usage:
    python run_job.py <job_id>
    python run_job.py <job_id> --url https://youtube.com/...
    python run_job.py --list          # show recent jobs and their status

Useful for reproducing failures that only show up in the bundled app, where
subprocess crashes are hard to observe. All output goes to stdout so you can
see exactly what the pipeline is doing.
"""

import argparse
import os
import sys
from pathlib import Path

# Add the backend to sys.path
BACKEND = Path(__file__).parent
sys.path.insert(0, str(BACKEND))

DATA_DIR = Path.home() / "Library" / "Application Support" / "MusicTranscriber"
os.environ.setdefault("MT_DATA_DIR", str(DATA_DIR))
os.environ.setdefault(
    "MT_WEB_DIR",
    str(BACKEND / "packaging" / "_build" / "macos" / "MusicTranscriber.app"
        / "Contents" / "Resources" / "web"),
)

# Point at bundled ffmpeg if available
for _ffmpeg_candidate in [
    BACKEND / "packaging" / "_build" / "macos" / "MusicTranscriber.app"
    / "Contents" / "Resources" / "ffmpeg",
    Path("/Applications/MusicTranscriber.app/Contents/Resources/ffmpeg"),
]:
    if _ffmpeg_candidate.exists():
        os.environ["PATH"] = str(_ffmpeg_candidate.parent) + os.pathsep + os.environ.get("PATH", "")
        break


def _list_jobs():
    from api.database.session import SessionLocal
    db = SessionLocal()
    try:
        from api.database.models import Job
        jobs = db.query(Job).order_by(Job.created_at.desc()).limit(20).all()
        if not jobs:
            print("No jobs found.")
            return
        print(f"{'ID':<38} {'STATUS':<12} {'TITLE'}")
        print("-" * 80)
        for j in jobs:
            title = (j.title or j.original_filename or j.source_url or "")[:40]
            print(f"{j.id:<38} {j.status.value:<12} {title}")
    finally:
        db.close()


def _run_job(job_id: str, source_url: str | None):
    from api.utils.logging import setup_logging
    setup_logging()

    from api.database.session import SessionLocal
    from api.database.models import JobStatus
    from api.services.job_manager import JobManager

    db = SessionLocal()
    try:
        job = JobManager.get_job(db, job_id)
    except Exception as e:
        print(f"Job not found: {e}")
        sys.exit(1)
    finally:
        db.close()

    print(f"Job      : {job.id}")
    print(f"Status   : {job.status.value}")
    print(f"Title    : {job.title or job.original_filename or '—'}")
    print(f"Source   : {job.source_url or job.input_file_path or '—'}")
    print()

    # Reset to failed so the worker can update it
    db = SessionLocal()
    try:
        JobManager.reset_job_for_retry(db, job_id)
    except Exception:
        pass
    finally:
        db.close()

    effective_url = source_url or job.source_url
    input_path = Path(job.input_file_path) if job.input_file_path else None
    if input_path and not input_path.exists():
        print(f"Input file missing: {input_path}")
        if not effective_url:
            print("No source URL either — cannot redownload.")
            sys.exit(1)
        print(f"Will re-download from: {effective_url}")
        input_path = None

    print("Running pipeline (blocking — Ctrl+C to abort)...\n")

    from api.routes.transcription import run_pipeline_task
    run_pipeline_task(
        job_id=job_id,
        input_audio_path=input_path,
        source_url=effective_url,
    )
    print("\nDone.")


def main():
    parser = argparse.ArgumentParser(description="MusicTranscriber job debug runner")
    parser.add_argument("job_id", nargs="?", help="Job UUID to run")
    parser.add_argument("--url", help="Override/supply source URL")
    parser.add_argument("--list", action="store_true", help="List recent jobs")
    args = parser.parse_args()

    if args.list or not args.job_id:
        _list_jobs()
        return

    _run_job(args.job_id, args.url)


if __name__ == "__main__":
    main()
