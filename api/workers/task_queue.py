import asyncio
import multiprocessing
import shutil
import threading
from pathlib import Path
from typing import Dict, Optional, Set

from api.utils.logging import get_logger
from api.config import settings

logger = get_logger("task_queue")

# Use spawn explicitly — safe with MPS/Metal and async code.
# fork is dangerous with MPS GPU state and uvicorn's event loop.
_mp_context = multiprocessing.get_context("spawn")


class TaskQueue:

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self._processes: Dict[str, _mp_context.Process] = {}
        self._active_jobs: Set[str] = set()
        self._lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self._start_monitor()
        logger.info(
            f"TaskQueue initialized with process-based execution "
            f"(max {settings.max_concurrent_jobs} concurrent jobs)"
        )

    def _start_monitor(self):
        """Daemon thread that watches for completed/crashed processes and
        removes them from the active set."""

        def _monitor():
            while not self._shutdown_event.is_set():
                with self._lock:
                    completed = [
                        jid
                        for jid, proc in self._processes.items()
                        if not proc.is_alive()
                    ]
                    for jid in completed:
                        proc = self._processes.pop(jid)
                        self._active_jobs.discard(jid)
                        exitcode = proc.exitcode
                        if exitcode == 0:
                            logger.info(
                                f"Job {jid} process completed successfully (exit 0) "
                                f"({len(self._active_jobs)}/{settings.max_concurrent_jobs} active)"
                            )
                        elif exitcode == -9:
                            # SIGKILL — expected for cancelled jobs
                            logger.info(f"Job {jid} process was killed (SIGKILL)")
                        else:
                            logger.error(
                                f"Job {jid} process exited unexpectedly (exit {exitcode})"
                            )
                self._shutdown_event.wait(timeout=1.0)

        t = threading.Thread(
            target=_monitor, daemon=True, name="task_queue_monitor"
        )
        t.start()

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
        """Spawn a new OS process for the job.

        All args/kwargs must be picklable (required by spawn start method).
        """
        with self._lock:
            # Access _active_jobs directly — do NOT call can_accept_job() or
            # is_job_active() here. Those methods acquire self._lock themselves,
            # and threading.Lock is not reentrant, causing a self-deadlock.
            if len(self._active_jobs) >= settings.max_concurrent_jobs:
                raise RuntimeError(
                    f"Task queue is full ({settings.max_concurrent_jobs} jobs)"
                )
            if job_id in self._active_jobs:
                raise RuntimeError(f"Job {job_id} is already running")

            process = _mp_context.Process(
                target=task_func,
                args=args,
                kwargs=kwargs,
                name=f"pipeline_{job_id}",
                daemon=False,
            )
            self._processes[job_id] = process
            self._active_jobs.add(job_id)

        logger.info(
            f"Spawning process for job {job_id} "
            f"({self.get_active_job_count()}/{settings.max_concurrent_jobs})"
        )
        # process.start() with spawn bootstraps a fresh Python interpreter.
        # Run in executor so it doesn't block the asyncio event loop.
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, process.start)
        logger.info(f"Process started for job {job_id} (pid={process.pid})")

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def cancel_job(
        self, job_id: str, job_storage_path: Optional[Path] = None
    ) -> bool:
        """Send SIGKILL to the job's process and clean up its storage.

        SIGKILL cannot be caught or ignored — it terminates the process
        immediately regardless of what C extension or GPU kernel is running.
        """
        with self._lock:
            process = self._processes.get(job_id)
            if not process:
                return False

            if process.is_alive():
                process.kill()
                process.join(timeout=5)
                logger.info(f"Job {job_id} process killed")

            self._processes.pop(job_id, None)
            self._active_jobs.discard(job_id)

        # Clean up storage outside the lock — shutil.rmtree can take a moment
        if job_storage_path:
            storage = Path(job_storage_path)
            if storage.exists():
                shutil.rmtree(storage, ignore_errors=True)
                logger.info(f"Cleaned up storage for cancelled job {job_id}: {storage}")

        return True

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self, wait: bool = True, timeout: float = 30):
        active = self.get_active_job_count()
        if active:
            logger.info(
                f"Shutting down task queue with {active} active job(s), "
                f"{'waiting' if wait else 'killing immediately'}..."
            )
        else:
            logger.info("Shutting down task queue (no active jobs)...")

        self._shutdown_event.set()

        with self._lock:
            processes = list(self._processes.items())

        for job_id, process in processes:
            if not process.is_alive():
                continue
            if wait:
                logger.info(f"Waiting for job {job_id} to finish (up to {timeout}s)...")
                process.join(timeout=timeout)
                if process.is_alive():
                    logger.warning(
                        f"Job {job_id} did not finish in {timeout}s — killing"
                    )
                    process.kill()
                    process.join(timeout=5)
            else:
                process.kill()
                process.join(timeout=5)

        with self._lock:
            self._processes.clear()
            self._active_jobs.clear()

        logger.info("Task queue shutdown complete")

    def get_queue_status(self) -> dict:
        with self._lock:
            return {
                "active_jobs": len(self._active_jobs),
                "max_concurrent_jobs": settings.max_concurrent_jobs,
                "can_accept_jobs": self.can_accept_job(),
                "active_job_ids": list(self._active_jobs),
            }


task_queue = TaskQueue()
