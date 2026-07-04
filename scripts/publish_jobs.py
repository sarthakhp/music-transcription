#!/usr/bin/env python3
"""Publish completed jobs to Firebase Storage.

Usage:
    python scripts/publish_jobs.py            # publish all completed jobs
    python scripts/publish_jobs.py <job_id>   # publish a single job

Requires firebase_credentials_path and firebase_storage_bucket to be set
(via .env or environment).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.database.session import SessionLocal
from api.database.models import Job, JobStatus
from api.services import storage_publisher


def main() -> int:
    if not storage_publisher.is_configured():
        print(
            "ERROR: Firebase is not configured. Set firebase_credentials_path and "
            "firebase_storage_bucket in your .env."
        )
        return 1

    db = SessionLocal()
    try:
        if len(sys.argv) > 1:
            job_ids = [sys.argv[1]]
        else:
            jobs = (
                db.query(Job)
                .filter(Job.status == JobStatus.COMPLETED)
                .order_by(Job.created_at.desc())
                .all()
            )
            job_ids = [j.id for j in jobs]

        if not job_ids:
            print("No completed jobs to publish.")
            return 0

        print(f"Publishing {len(job_ids)} job(s)...")
        ok, failed = 0, 0
        for job_id in job_ids:
            try:
                manifest = storage_publisher.publish_job(db, job_id)
                print(f"  ✓ {job_id} — {manifest['title']}")
                ok += 1
            except Exception as e:
                print(f"  ✗ {job_id} — {e}")
                failed += 1

        print(f"Done: {ok} published, {failed} failed.")
        return 0 if failed == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
