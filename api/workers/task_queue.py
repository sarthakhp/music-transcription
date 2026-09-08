import asyncio
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict, Optional, Set

from api.utils.logging import get_logger
from api.config import settings

logger = get_logger("task_queue")

_RUNNER = Path(__file__).parent / "job_runner.py"
_PYTHON = sys.executable  # venv python that started this process


class TaskQueue:

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self._processes: Dict[str, subprocess.Popen] = {}
        self._active_jobs: Set[str] = set()
        self._lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self._start_monitor()
        logger.info(
            f"TaskQueue initialized (max {settings.max_concurrent_jobs} concurrent jobs)"
        )

    def _start_monitor(self):
        def _monitor():
            while not self._shutdown_event.is_set():
                with self._lock:
                    completed = [
                        jid
                        for jid, proc in self._processes.items()
                        if proc.poll() is not None
                    ]
                    for jid in completed:
                        proc = self._processes.pop(jid)
                        self._active_jobs.discard(jid)
                        rc = proc.returncode
                        if rc == 0:
                            logger.info(
                                f"Job {jid} completed (exit 0) "
                                f"({len(self._active_jobs)}/{settings.max_concurrent_jobs} active)"
                            )
                        elif rc == -9:
                            logger.info(f"Job {jid} killed (SIGKILL)")
                        else:
                            log_path = settings.log_file.parent / f"job_{jid}.log"
                            tail = ""
                            try:
                                lines = log_path.read_text(errors="replace").splitlines()
                                tail = "\n".join(lines[-40:])
                            except Exception:
                                pass
                            logger.error(
                                f"Job {jid} process exited unexpectedly (exit {rc})"
                                + (f"\n--- job log ---\n{tail}\n--- end ---" if tail else " (no log)")
                            )
                self._shutdown_event.wait(timeout=1.0)

        threading.Thread(target=_monitor, daemon=True, name="task_queue_monitor").start()

    # ------------------------------------------------------------------
    # Queue state
    # ------------------------------------------------------------------

    def is_job_active(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._active_jobs

    def get_active_job_count(self) -> int:
        with self._lock:
            return len(self._active_jobs)

    def can_accept_job(self) -> bool:
        return self.get_active_job_count() < settings.max_concurrent_jobs

    # ------------------------------------------------------------------
    # Job submission
    # ------------------------------------------------------------------

    async def submit_job(self, job_id: str, task_func, *args, **kwargs):
        """Launch job_runner.py as a subprocess.

        Uses subprocess.Popen instead of multiprocessing.Process to avoid
        Python's spawn bootstrap re-running uvicorn's __main__ module.
        All stdout+stderr go to a per-job log file for easy debugging.
        """
        with self._lock:
            if len(self._active_jobs) >= settings.max_concurrent_jobs:
                raise RuntimeError(f"Task queue full ({settings.max_concurrent_jobs} jobs)")
            if job_id in self._active_jobs:
                raise RuntimeError(f"Job {job_id} is already running")

            log_path = settings.log_file.parent / f"job_{job_id}.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # Build CLI args from positional args and kwargs.
            # submit_job is called as: submit_job(job_id, func, job_id, input_path,
            #   trace_id=..., source_url=..., separation_model=...)
            # args[0] = job_id, args[1] = input_audio_path
            job_id_arg = args[0] if args else job_id
            input_path = args[1] if len(args) > 1 else None
            trace_id = kwargs.get("trace_id")
            source_url = kwargs.get("source_url")
            separation_model = kwargs.get("separation_model")
            start_time = kwargs.get("start_time")
            end_time = kwargs.get("end_time")

            cmd = [_PYTHON, str(_RUNNER), str(job_id_arg)]
            if input_path:
                cmd += ["--input-path", str(input_path)]
            if source_url:
                cmd += ["--source-url", source_url]
            if trace_id:
                cmd += ["--trace-id", trace_id]
            if separation_model:
                cmd += ["--separation-model", separation_model]
            if start_time is not None:
                cmd += ["--start-time", str(start_time)]
            if end_time is not None:
                cmd += ["--end-time", str(end_time)]

            log_fd = open(log_path, "w")
            proc = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=log_fd,
                cwd=str(_RUNNER.parent.parent.parent),  # backend dir
            )
            log_fd.close()  # parent doesn't need the fd; subprocess has it

            self._processes[job_id] = proc
            self._active_jobs.add(job_id)

        logger.info(
            f"Launched job {job_id} (pid={proc.pid}, log={log_path.name}) "
            f"({self.get_active_job_count()}/{settings.max_concurrent_jobs})"
        )

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def cancel_job(self, job_id: str, job_storage_path: Optional[Path] = None) -> bool:
        with self._lock:
            proc = self._processes.get(job_id)
            if not proc:
                return False

            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
                logger.info(f"Job {job_id} killed")

            self._processes.pop(job_id, None)
            self._active_jobs.discard(job_id)

        if job_storage_path:
            storage = Path(job_storage_path)
            if storage.exists():
                shutil.rmtree(storage, ignore_errors=True)
                logger.info(f"Cleaned up storage for cancelled job {job_id}")

        return True

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self, wait: bool = True, timeout: float = 30):
        active = self.get_active_job_count()
        logger.info(
            f"Shutting down task queue "
            f"({'no active jobs' if not active else f'{active} active job(s)'})"
        )
        self._shutdown_event.set()

        with self._lock:
            processes = list(self._processes.items())

        for job_id, proc in processes:
            if proc.poll() is not None:
                continue
            if wait:
                logger.info(f"Waiting for job {job_id} (up to {timeout}s)...")
                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Job {job_id} timed out — killing")
                    proc.kill()
                    proc.wait(timeout=5)
            else:
                proc.kill()
                proc.wait(timeout=5)

        with self._lock:
            self._processes.clear()
            self._active_jobs.clear()

        logger.info("Task queue shutdown complete")

    def get_queue_status(self) -> dict:
        with self._lock:
            active = len(self._active_jobs)
            return {
                "active_jobs": active,
                "max_concurrent_jobs": settings.max_concurrent_jobs,
                "can_accept_jobs": active < settings.max_concurrent_jobs,
                "active_job_ids": list(self._active_jobs),
            }


task_queue = TaskQueue()
