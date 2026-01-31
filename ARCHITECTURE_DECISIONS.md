# Architecture Decision Record (ADR)
## FastAPI Backend for Music Transcription Pipeline

**Date:** 2026-01-31  
**Status:** Proposed

---

## Decision Matrix

This document outlines key architectural decisions that need to be made during implementation.

---

## 1. Job Queue System

### Options

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **FastAPI BackgroundTasks** | ✅ Simple, no external dependencies<br>✅ Easy to implement<br>✅ Good for single server | ❌ Not distributed<br>❌ Jobs lost on restart<br>❌ Limited scalability | **START HERE** - Good for MVP |
| **Celery + Redis** | ✅ Distributed<br>✅ Persistent queue<br>✅ Highly scalable<br>✅ Task retry support | ❌ More complex setup<br>❌ Additional infrastructure<br>❌ Learning curve | **MIGRATE LATER** - When scaling needed |
| **RQ (Redis Queue)** | ✅ Simpler than Celery<br>✅ Python-native<br>✅ Good monitoring | ❌ Requires Redis<br>❌ Less features than Celery | Alternative to Celery |

### Decision: **Start with BackgroundTasks, plan for Celery migration**

**Rationale:**
- MVP can use BackgroundTasks for simplicity
- Design code to be queue-agnostic
- Migrate to Celery when concurrent users > 10 or need job persistence

**Implementation:**
```python
# Design pattern - queue agnostic
class JobQueue(ABC):
    @abstractmethod
    async def enqueue(self, job_id: str, audio_path: Path): pass

class BackgroundTaskQueue(JobQueue):
    async def enqueue(self, job_id: str, audio_path: Path):
        background_tasks.add_task(process_pipeline, job_id, audio_path)

class CeleryQueue(JobQueue):  # Future implementation
    async def enqueue(self, job_id: str, audio_path: Path):
        process_pipeline.delay(job_id, str(audio_path))
```

---

## 2. Database Selection

### Options

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **SQLite** | ✅ Zero configuration<br>✅ File-based<br>✅ Perfect for development | ❌ Not for production<br>❌ No concurrent writes<br>❌ Limited scalability | **DEVELOPMENT ONLY** |
| **PostgreSQL** | ✅ Production-ready<br>✅ ACID compliant<br>✅ Excellent performance<br>✅ JSON support | ❌ Requires setup<br>❌ More complex | **PRODUCTION** |
| **MySQL** | ✅ Widely used<br>✅ Good performance | ❌ Less JSON support<br>❌ Licensing concerns | Not recommended |

### Decision: **SQLite for dev, PostgreSQL for production**

**Rationale:**
- SQLite allows rapid development without setup
- PostgreSQL is industry standard for production
- SQLAlchemy makes switching databases trivial

**Implementation:**
```python
# api/config.py
class Settings(BaseSettings):
    database_url: str = Field(
        default="sqlite:///./api.db",
        env="DATABASE_URL"
    )
    
# Production .env
DATABASE_URL=postgresql://user:pass@localhost/musicapi
```

---

## 3. Authentication & Authorization

### Options

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **No Auth** | ✅ Simplest<br>✅ Fastest development | ❌ No security<br>❌ Public access | **MVP ONLY** - Internal use |
| **API Key** | ✅ Simple to implement<br>✅ Good for mobile apps<br>✅ Easy to revoke | ❌ Keys can leak<br>❌ No user context | **RECOMMENDED** - Phase 2 |
| **JWT (OAuth2)** | ✅ Stateless<br>✅ Industry standard<br>✅ User context | ❌ More complex<br>❌ Token management | Future enhancement |

### Decision: **No auth for MVP, API Key for production**

**Rationale:**
- Start without auth to focus on core functionality
- Add API key authentication before public deployment
- JWT can be added later if user management needed

**Implementation Plan:**
```python
# Phase 1: No auth
@router.post("/transcribe")
async def transcribe_audio(file: UploadFile): pass

# Phase 2: API Key
from fastapi.security import APIKeyHeader
api_key_header = APIKeyHeader(name="X-API-Key")

@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile,
    api_key: str = Depends(api_key_header)
): pass
```

---

## 4. File Storage

### Options

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **Local Filesystem** | ✅ Simple<br>✅ Fast access<br>✅ No external deps | ❌ Not scalable<br>❌ Single server only<br>❌ Backup complexity | **START HERE** |
| **S3 / MinIO** | ✅ Scalable<br>✅ Distributed<br>✅ Built-in backup<br>✅ CDN integration | ❌ Network latency<br>❌ Additional cost<br>❌ More complex | **PRODUCTION** - When scaling |
| **NFS / Network Storage** | ✅ Shared across servers<br>✅ Centralized | ❌ Network dependency<br>❌ Performance overhead | Alternative |

### Decision: **Local filesystem with S3-compatible interface**

**Rationale:**
- Start with local storage for simplicity
- Design storage layer to be pluggable
- Easy migration to S3 when needed

**Implementation:**
```python
# api/services/storage.py
class StorageBackend(ABC):
    @abstractmethod
    async def save(self, path: str, data: bytes): pass
    @abstractmethod
    async def get(self, path: str) -> bytes: pass

class LocalStorage(StorageBackend):
    async def save(self, path: str, data: bytes):
        Path(path).write_bytes(data)

class S3Storage(StorageBackend):  # Future
    async def save(self, path: str, data: bytes):
        await s3_client.put_object(Bucket=bucket, Key=path, Body=data)
```

---

## 5. Progress Tracking

### Options

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **Database Polling** | ✅ Simple<br>✅ Works everywhere<br>✅ No extra infrastructure | ❌ Polling overhead<br>❌ Not real-time<br>❌ Client complexity | **MVP** - Good enough |
| **WebSocket** | ✅ Real-time updates<br>✅ Efficient<br>✅ Better UX | ❌ More complex<br>❌ Connection management<br>❌ Firewall issues | **ENHANCEMENT** - Phase 2 |
| **Server-Sent Events (SSE)** | ✅ Real-time<br>✅ Simpler than WebSocket<br>✅ HTTP-based | ❌ One-way only<br>❌ Browser limitations | Alternative |

### Decision: **Database polling for MVP, WebSocket for enhancement**

**Rationale:**
- Polling is sufficient for 2-3 minute processing times
- WebSocket adds complexity not needed initially
- Can add WebSocket later without breaking existing clients

**Implementation:**
```python
# MVP: Client polls every 2 seconds
GET /api/v1/jobs/{job_id}  # Returns current progress

# Future: WebSocket endpoint
@app.websocket("/ws/jobs/{job_id}")
async def job_progress_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()
    while True:
        progress = get_job_progress(job_id)
        await websocket.send_json(progress)
        await asyncio.sleep(1)
```

---

## 6. Concurrent Job Limits

### Decision: **Limit to 2-3 concurrent jobs initially**

**Rationale:**
- GPU memory constraints (8-10GB per job)
- Processing time (2-3 minutes per job)
- Better to queue than to crash

**Implementation:**
```python
# api/config.py
MAX_CONCURRENT_JOBS = 3

# api/services/job_manager.py
def can_start_new_job(self) -> bool:
    active_jobs = self.db.query(Job).filter(
        Job.status == JobStatus.PROCESSING
    ).count()
    return active_jobs < MAX_CONCURRENT_JOBS
```

---

## 7. Error Handling Strategy

### Decision: **Fail fast with detailed error messages**

**Approach:**
1. Validate inputs early (file format, size)
2. Catch all exceptions in pipeline
3. Store error details in database
4. Return user-friendly error messages
5. Log full stack traces for debugging

**Implementation:**
```python
try:
    result = await process_pipeline(job_id, audio_path)
except InvalidAudioFileException as e:
    job_manager.update_status(job_id, JobStatus.FAILED, 
                              error_message=str(e))
except Exception as e:
    logger.exception(f"Pipeline failed for job {job_id}")
    job_manager.update_status(job_id, JobStatus.FAILED,
                              error_message="Internal processing error")
```

---

## 8. API Versioning

### Decision: **Use URL path versioning (/api/v1/)**

**Rationale:**
- Clear and explicit
- Easy to maintain multiple versions
- Standard practice

**Implementation:**
```python
# Current
router = APIRouter(prefix="/api/v1")

# Future v2 (if needed)
router_v2 = APIRouter(prefix="/api/v2")
```

---

## Summary of Decisions

| Decision Area | MVP Choice | Production Choice | Migration Trigger |
|--------------|------------|-------------------|-------------------|
| Job Queue | BackgroundTasks | Celery + Redis | > 10 concurrent users |
| Database | SQLite | PostgreSQL | Production deployment |
| Authentication | None | API Key | Public deployment |
| Storage | Local FS | S3/MinIO | Multi-server deployment |
| Progress | Polling | WebSocket | User feedback |
| Concurrent Jobs | 2-3 | Auto-scaling | Resource monitoring |

---

## Next Review

Review these decisions after:
- [ ] Phase 4 completion (pipeline integration)
- [ ] First production deployment
- [ ] 100 jobs processed
- [ ] User feedback received

**Last Updated:** 2026-01-31

