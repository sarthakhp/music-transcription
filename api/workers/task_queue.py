import asyncio
from typing import Dict, Set
from concurrent.futures import ThreadPoolExecutor
from api.utils.logging import get_logger
from api.config import settings

logger = get_logger("task_queue")


class TaskQueue:
    
    _instance = None
    _executor: ThreadPoolExecutor = None
    _active_jobs: Set[str] = set()
    _job_futures: Dict[str, asyncio.Future] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskQueue, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        self._executor = ThreadPoolExecutor(
            max_workers=settings.max_concurrent_jobs,
            thread_name_prefix="pipeline_worker"
        )
        self._active_jobs = set()
        self._job_futures = {}
        logger.info(f"TaskQueue initialized with {settings.max_concurrent_jobs} workers")
    
    def is_job_active(self, job_id: str) -> bool:
        return job_id in self._active_jobs
    
    def get_active_job_count(self) -> int:
        return len(self._active_jobs)
    
    def can_accept_job(self) -> bool:
        return self.get_active_job_count() < settings.max_concurrent_jobs
    
    async def submit_job(self, job_id: str, task_func, *args, **kwargs):
        if not self.can_accept_job():
            raise RuntimeError(f"Task queue is full ({settings.max_concurrent_jobs} jobs)")
        
        if self.is_job_active(job_id):
            raise RuntimeError(f"Job {job_id} is already running")
        
        self._active_jobs.add(job_id)
        logger.info(f"Submitting job {job_id} to task queue ({self.get_active_job_count()}/{settings.max_concurrent_jobs})")
        
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(self._executor, task_func, *args, **kwargs)
        self._job_futures[job_id] = future
        
        future.add_done_callback(lambda f: self._on_job_complete(job_id, f))
        
        return future
    
    def _on_job_complete(self, job_id: str, future: asyncio.Future):
        if job_id in self._active_jobs:
            self._active_jobs.remove(job_id)
        
        if job_id in self._job_futures:
            del self._job_futures[job_id]
        
        try:
            result = future.result()
            logger.info(f"Job {job_id} completed successfully ({self.get_active_job_count()}/{settings.max_concurrent_jobs} active)")
        except Exception as e:
            logger.error(f"Job {job_id} failed with error: {str(e)}")
    
    def cancel_job(self, job_id: str) -> bool:
        if job_id not in self._job_futures:
            return False
        
        future = self._job_futures[job_id]
        cancelled = future.cancel()
        
        if cancelled:
            if job_id in self._active_jobs:
                self._active_jobs.remove(job_id)
            if job_id in self._job_futures:
                del self._job_futures[job_id]
            logger.info(f"Job {job_id} cancelled")
        
        return cancelled
    
    def shutdown(self, wait: bool = True):
        logger.info("Shutting down task queue...")
        self._executor.shutdown(wait=wait)
        logger.info("Task queue shutdown complete")
    
    def get_queue_status(self) -> dict:
        return {
            "active_jobs": len(self._active_jobs),
            "max_concurrent_jobs": settings.max_concurrent_jobs,
            "can_accept_jobs": self.can_accept_job(),
            "active_job_ids": list(self._active_jobs)
        }


task_queue = TaskQueue()

