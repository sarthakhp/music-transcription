"""Standalone entry point for a single pipeline job.

Run by task_queue.py via subprocess.Popen — never imported by the server.
All output (stdout + stderr) goes to the job log file.

Usage:
    python job_runner.py <job_id> [--input-path PATH] [--source-url URL]
                                   [--trace-id ID] [--separation-model KEY]
"""
import argparse
import os
import sys
from pathlib import Path

# Add backend dir to path so all api.* imports work.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("job_id")
    parser.add_argument("--input-path", default=None)
    parser.add_argument("--source-url", default=None)
    parser.add_argument("--trace-id", default=None)
    parser.add_argument("--separation-model", default=None)
    parser.add_argument("--start-time", type=float, default=None)
    parser.add_argument("--end-time", type=float, default=None)
    args = parser.parse_args()

    from api.routes.transcription import run_pipeline_task
    run_pipeline_task(
        job_id=args.job_id,
        input_audio_path=Path(args.input_path) if args.input_path else None,
        source_url=args.source_url,
        trace_id=args.trace_id,
        separation_model=args.separation_model,
        start_time=args.start_time,
        end_time=args.end_time,
    )


if __name__ == "__main__":
    main()
