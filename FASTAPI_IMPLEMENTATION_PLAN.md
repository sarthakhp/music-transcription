# FastAPI Backend Implementation Plan
## Music Transcription Pipeline API

**Version:** 1.0  
**Date:** 2026-01-31  
**Status:** Planning Phase

---

## 📋 Executive Summary

This document outlines the implementation plan for converting the existing music transcription pipeline into a production-ready FastAPI backend service. The backend will accept audio files from a Flutter frontend, process them through a 3-stage pipeline (source separation, vocal transcription, chord detection), and return separated audio stems, processed frames JSON, and chords JSON.

### Key Objectives
- ✅ Create RESTful API for audio processing
- ✅ Implement async job processing for long-running tasks
- ✅ Provide real-time progress tracking
- ✅ Ensure scalability and resource management
- ✅ Maintain compatibility with existing pipeline code

### Timeline Estimate
- **Total Duration:** 3-4 weeks
- **Phase 1-3:** Week 1 (Core infrastructure)
- **Phase 4-5:** Week 2 (Pipeline integration)
- **Phase 6-7:** Week 3 (Testing & refinement)
- **Phase 8:** Week 4 (Production deployment)

---

## 🏗️ Architecture Overview

### System Components

```
┌─────────────────┐
│ Flutter Client  │
└────────┬────────┘
         │ HTTP/REST
         ▼
┌─────────────────────────────────────┐
│         FastAPI Server              │
│  ┌──────────────────────────────┐  │
│  │   API Endpoints Layer        │  │
│  │  - Upload                    │  │
│  │  - Status                    │  │
│  │  - Results                   │  │
│  └──────────┬───────────────────┘  │
│             ▼                       │
│  ┌──────────────────────────────┐  │
│  │   Job Management Layer       │  │
│  │  - Queue                     │  │
│  │  - Status Tracking           │  │
│  │  - Progress Updates          │  │
│  └──────────┬───────────────────┘  │
│             ▼                       │
│  ┌──────────────────────────────┐  │
│  │   Background Workers         │  │
│  │  - Source Separation         │  │
│  │  - Vocal Transcription       │  │
│  │  - Chord Detection           │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│      File Storage System            │
│  - Input audio files                │
│  - Separated stems (MP3)            │
│  - Processed frames (JSON)          │
│  - Chords data (JSON)               │
└─────────────────────────────────────┘
```

### Technology Stack

**Core Framework:**
- FastAPI 0.109+
- Uvicorn (ASGI server)
- Pydantic v2 (data validation)

**Job Processing:**
- Option A: FastAPI BackgroundTasks (simple, single-server)
- Option B: Celery + Redis (scalable, distributed)
- **Recommendation:** Start with BackgroundTasks, migrate to Celery if needed

**Storage:**
- Local filesystem (development)
- S3-compatible storage (production option)

**Database:**
- SQLite (development)
- PostgreSQL (production)
- Purpose: Job metadata, status tracking

**Existing Pipeline:**
- All current dependencies from requirements.txt
- No changes to core ML models

---

## 📦 Project Structure

```
music-transcription/
├── api/                          # NEW: FastAPI application
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entry point
│   ├── config.py                 # Configuration management
│   ├── dependencies.py           # Dependency injection
│   │
│   ├── models/                   # API data models
│   │   ├── __init__.py
│   │   ├── requests.py           # Request schemas
│   │   ├── responses.py          # Response schemas
│   │   └── job.py                # Job status models
│   │
│   ├── routes/                   # API endpoints
│   │   ├── __init__.py
│   │   ├── transcription.py      # Main transcription endpoints
│   │   ├── jobs.py               # Job status endpoints
│   │   └── health.py             # Health check endpoints
│   │
│   ├── services/                 # Business logic
│   │   ├── __init__.py
│   │   ├── job_manager.py        # Job queue & status
│   │   ├── pipeline_runner.py    # Pipeline orchestration
│   │   ├── file_manager.py       # File upload/storage
│   │   └── progress_tracker.py   # Progress updates
│   │
│   ├── workers/                  # Background processing
│   │   ├── __init__.py
│   │   └── pipeline_worker.py    # Async pipeline execution
│   │
│   ├── database/                 # Database layer
│   │   ├── __init__.py
│   │   ├── models.py             # SQLAlchemy models
│   │   └── session.py            # DB session management
│   │
│   └── utils/                    # Utilities
│       ├── __init__.py
│       ├── logging.py            # Logging configuration
│       └── exceptions.py         # Custom exceptions
│
├── src/                          # EXISTING: Pipeline code
│   ├── source_separation/
│   ├── vocal_transcription/
│   └── chord_detection/
│
├── storage/                      # NEW: File storage
│   └── jobs/
│       └── {job_id}/
│           ├── input/
│           ├── separated/
│           ├── transcription/
│           └── chords/
│
├── tests/                        # NEW: API tests
│   ├── test_api/
│   ├── test_services/
│   └── test_integration/
│
├── requirements.txt              # EXISTING: Pipeline deps
├── requirements-api.txt          # NEW: API-specific deps
├── .env.example                  # NEW: Environment template
├── docker-compose.yml            # NEW: Docker setup
└── README_API.md                 # NEW: API documentation
```

---

## 🎯 Implementation Phases

### Phase 1: Project Setup & Core Infrastructure
**Duration:** 2-3 days
**Priority:** Critical

#### Tasks
1. **Create API directory structure**
   - Set up `api/` folder with all subdirectories
   - Create `__init__.py` files
   - Set up proper Python package structure

2. **Install and configure FastAPI**
   - Create `requirements-api.txt`
   - Install FastAPI, Uvicorn, Pydantic
   - Set up basic FastAPI app in `api/main.py`

3. **Configuration management**
   - Create `api/config.py` with Settings class
   - Use Pydantic BaseSettings for environment variables
   - Define configuration for:
     - Server settings (host, port)
     - Storage paths
     - Processing limits (max file size, concurrent jobs)
     - Model paths
     - CORS settings

4. **Database setup**
   - Choose database (SQLite for dev, PostgreSQL for prod)
   - Install SQLAlchemy
   - Create database models for jobs
   - Set up Alembic for migrations

5. **Logging configuration**
   - Configure structured logging
   - Set up log rotation
   - Create logging utilities

#### Deliverables
- ✅ Working FastAPI server (basic "Hello World")
- ✅ Configuration system
- ✅ Database connection
- ✅ Logging infrastructure

#### Acceptance Criteria
- Server starts without errors
- Can access `/docs` for Swagger UI
- Environment variables load correctly
- Database migrations run successfully

---

### Phase 2: Job Management System
**Duration:** 3-4 days
**Priority:** Critical

#### Tasks
1. **Design job data model**
   ```python
   class Job:
       id: UUID
       status: JobStatus  # queued, processing, completed, failed
       stage: ProcessingStage  # separation, transcription, chords
       progress: int  # 0-100
       created_at: datetime
       started_at: Optional[datetime]
       completed_at: Optional[datetime]
       error_message: Optional[str]
       input_filename: str
       file_size: int
   ```

2. **Implement JobManager service**
   - Create job creation
   - Update job status
   - Query job by ID
   - List jobs (with pagination)
   - Delete old jobs (cleanup)

3. **Progress tracking system**
   - Create ProgressTracker class
   - Implement stage-based progress (0-33%, 33-66%, 66-100%)
   - Add callback mechanism for pipeline updates

4. **Background task infrastructure**
   - Set up FastAPI BackgroundTasks
   - Create worker function wrapper
   - Implement error handling in background tasks

5. **Job storage management**
   - Create directory structure per job
   - Implement file path helpers
   - Add cleanup utilities

#### Deliverables
- ✅ Job database model
- ✅ JobManager service
- ✅ Progress tracking system
- ✅ Background task runner

#### Acceptance Criteria
- Can create and track jobs
- Progress updates work correctly
- Background tasks execute without blocking API
- Job cleanup works properly

---

### Phase 3: API Endpoints Implementation
**Duration:** 3-4 days
**Priority:** Critical

#### Tasks
1. **Define Pydantic models**
   - Request models (upload, query params)
   - Response models (job status, results)
   - Error response models

2. **Implement core endpoints**

   **POST /api/v1/transcribe**
   - Accept multipart file upload
   - Validate file type (mp3, wav, m4a, etc.)
   - Validate file size (max 100MB)
   - Create job record
   - Save uploaded file
   - Queue background task
   - Return job_id

   **GET /api/v1/jobs/{job_id}**
   - Retrieve job status
   - Return progress information
   - Include stage details

   **GET /api/v1/jobs/{job_id}/results**
   - Check if job is completed
   - Return URLs/paths to all outputs
   - Include metadata

   **GET /api/v1/jobs/{job_id}/stems/{stem_name}**
   - Validate stem name
   - Return MP3 file
   - Set proper content-type headers

   **GET /api/v1/jobs/{job_id}/frames**
   - Return processed frames JSON
   - Stream large files

   **GET /api/v1/jobs/{job_id}/chords**
   - Return chords JSON

   **DELETE /api/v1/jobs/{job_id}**
   - Delete job and all associated files
   - Return confirmation

3. **Health check endpoints**
   - GET /health - Basic health check
   - GET /health/ready - Readiness probe
   - GET /health/live - Liveness probe

4. **CORS configuration**
   - Configure allowed origins for Flutter app
   - Set up proper headers

#### Deliverables
- ✅ All API endpoints implemented
- ✅ Request/response validation
- ✅ OpenAPI documentation
- ✅ CORS configured

#### Acceptance Criteria
- All endpoints return correct status codes
- File uploads work correctly
- Validation errors return 422 with details
- Swagger UI shows all endpoints
- CORS allows Flutter app requests

---

### Phase 4: Pipeline Integration
**Duration:** 4-5 days
**Priority:** Critical

#### Tasks
1. **Create PipelineRunner service**
   - Wrap existing pipeline functions
   - Add progress callbacks
   - Implement error handling
   - Add logging at each stage

2. **Refactor pipeline for API use**
   - Modify `run_separation()` to accept callbacks
   - Modify `run_transcription()` to accept callbacks
   - Modify `run_chord_detection()` to accept callbacks
   - Make all functions return structured data

3. **Implement pipeline worker**
   ```python
   async def process_pipeline(job_id: str, audio_path: Path):
       # Update job status
       # Stage 1: Separation (0-33%)
       # Stage 2: Transcription (33-66%)
       # Stage 3: Chords (66-100%)
       # Handle errors
       # Update completion status
   ```

4. **Add progress reporting**
   - Report progress at key milestones
   - Update database with current stage
   - Calculate percentage completion

5. **Error handling and recovery**
   - Catch and log all exceptions
   - Update job status to 'failed'
   - Store error messages
   - Clean up partial outputs

6. **Resource management**
   - Implement concurrent job limits
   - Add GPU/MPS memory management
   - Clear cache between stages

#### Deliverables
- ✅ PipelineRunner service
- ✅ Integrated pipeline worker
- ✅ Progress reporting
- ✅ Error handling

#### Acceptance Criteria
- Full pipeline runs successfully via API
- Progress updates correctly
- Errors are caught and reported
- All outputs are generated
- Memory is managed properly

---

### Phase 5: File Storage & Management
**Duration:** 2-3 days
**Priority:** High

#### Tasks
1. **File upload handling**
   - Implement streaming upload for large files
   - Validate file format (use python-magic)
   - Check file size limits
   - Generate unique filenames

2. **Storage organization**
   - Create job-specific directories
   - Organize outputs by type
   - Implement path helpers

3. **File serving**
   - Implement secure file downloads
   - Add range request support (for streaming)
   - Set proper content-type headers
   - Add cache headers

4. **Cleanup mechanisms**
   - Implement job expiration (delete after N days)
   - Add manual cleanup endpoint
   - Create background cleanup task
   - Handle partial/failed job cleanup

5. **Storage monitoring**
   - Track disk usage
   - Implement storage limits
   - Add alerts for low disk space

#### Deliverables
- ✅ File upload system
- ✅ Storage organization
- ✅ File serving endpoints
- ✅ Cleanup system

#### Acceptance Criteria
- Large files upload successfully
- Files are organized correctly
- Downloads work with proper headers
- Old jobs are cleaned up automatically
- Storage limits are enforced

---

### Phase 6: Error Handling & Validation
**Duration:** 2-3 days
**Priority:** High

#### Tasks
1. **Input validation**
   - Validate audio file formats
   - Check file integrity
   - Validate request parameters
   - Add custom validators

2. **Error handling middleware**
   - Create global exception handler
   - Handle common errors (404, 422, 500)
   - Return consistent error format
   - Log all errors

3. **Custom exceptions**
   ```python
   class JobNotFoundException(Exception)
   class InvalidAudioFileException(Exception)
   class ProcessingFailedException(Exception)
   class StorageLimitExceededException(Exception)
   ```

4. **Validation error responses**
   - Return detailed validation errors
   - Include field-level error messages
   - Provide helpful error descriptions

5. **Logging enhancements**
   - Add request/response logging
   - Log pipeline execution details
   - Add performance metrics
   - Create error tracking

#### Deliverables
- ✅ Comprehensive validation
- ✅ Error handling middleware
- ✅ Custom exceptions
- ✅ Enhanced logging

#### Acceptance Criteria
- Invalid inputs return clear error messages
- All errors are logged properly
- Error responses follow consistent format
- No unhandled exceptions

---

### Phase 7: Testing & Documentation
**Duration:** 4-5 days
**Priority:** High

#### Tasks
1. **Unit tests**
   - Test JobManager service
   - Test FileManager service
   - Test PipelineRunner
   - Test utility functions
   - Target: 80%+ coverage

2. **Integration tests**
   - Test full pipeline execution
   - Test API endpoints
   - Test file upload/download
   - Test error scenarios

3. **API testing**
   - Test all endpoints with pytest
   - Test authentication (if added)
   - Test rate limiting (if added)
   - Test concurrent requests

4. **Load testing**
   - Test with multiple concurrent jobs
   - Test with large files
   - Measure response times
   - Identify bottlenecks

5. **API documentation**
   - Write comprehensive README_API.md
   - Document all endpoints
   - Provide example requests/responses
   - Create Postman collection

6. **Deployment documentation**
   - Write deployment guide
   - Document environment variables
   - Create Docker setup
   - Document monitoring setup

#### Deliverables
- ✅ Test suite (unit + integration)
- ✅ API documentation
- ✅ Deployment guide
- ✅ Postman collection

#### Acceptance Criteria
- All tests pass
- Code coverage > 80%
- Documentation is complete
- Examples work correctly

---

### Phase 8: Optimization & Production Readiness
**Duration:** 3-4 days
**Priority:** Medium

#### Tasks
1. **Performance optimization**
   - Add response caching
   - Optimize database queries
   - Implement connection pooling
   - Add request compression

2. **Security hardening**
   - Add rate limiting
   - Implement API key authentication (optional)
   - Add request size limits
   - Sanitize file uploads
   - Add HTTPS support

3. **Monitoring & observability**
   - Add Prometheus metrics
   - Set up health checks
   - Add performance monitoring
   - Create alerting rules

4. **Docker containerization**
   - Create Dockerfile
   - Create docker-compose.yml
   - Optimize image size
   - Add multi-stage builds

5. **Production configuration**
   - Set up environment-based config
   - Configure production database
   - Set up reverse proxy (nginx)
   - Configure SSL/TLS

6. **Scalability improvements**
   - Add Redis for job queue (optional)
   - Implement Celery workers (optional)
   - Add load balancing support
   - Document scaling strategies

#### Deliverables
- ✅ Optimized performance
- ✅ Security measures
- ✅ Monitoring setup
- ✅ Docker deployment
- ✅ Production configuration

#### Acceptance Criteria
- API responds quickly under load
- Security best practices implemented
- Monitoring dashboards available
- Docker deployment works
- Production-ready configuration

---

## 📊 API Specification

### Endpoint Summary

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/transcribe` | Upload audio and start processing | Optional |
| GET | `/api/v1/jobs/{job_id}` | Get job status and progress | Optional |
| GET | `/api/v1/jobs/{job_id}/results` | Get all results metadata | Optional |
| GET | `/api/v1/jobs/{job_id}/stems/{stem}` | Download separated stem | Optional |
| GET | `/api/v1/jobs/{job_id}/frames` | Download processed frames JSON | Optional |
| GET | `/api/v1/jobs/{job_id}/chords` | Download chords JSON | Optional |
| DELETE | `/api/v1/jobs/{job_id}` | Delete job and files | Optional |
| GET | `/health` | Health check | None |

### Data Models

#### Job Status Response
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "stage": "transcription",
  "progress": 45,
  "created_at": "2026-01-31T10:00:00Z",
  "started_at": "2026-01-31T10:00:05Z",
  "completed_at": null,
  "error_message": null,
  "input_filename": "song.mp3",
  "file_size": 5242880
}
```

#### Results Response
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "results": {
    "stems": {
      "vocals": "/api/v1/jobs/{job_id}/stems/vocals",
      "bass": "/api/v1/jobs/{job_id}/stems/bass",
      "drums": "/api/v1/jobs/{job_id}/stems/drums",
      "other": "/api/v1/jobs/{job_id}/stems/other",
      "instrumental": "/api/v1/jobs/{job_id}/stems/instrumental"
    },
    "processed_frames": "/api/v1/jobs/{job_id}/frames",
    "chords": "/api/v1/jobs/{job_id}/chords",
    "metadata": {
      "duration": 180.5,
      "tempo_bpm": 120.0,
      "num_frames": 18050,
      "num_chords": 45
    }
  }
}
```

---

## 🔧 Technical Specifications

### System Requirements

**Development:**
- Python 3.10+
- 16GB RAM minimum
- Apple Silicon Mac (for MPS) or NVIDIA GPU
- 50GB free disk space

**Production:**
- Python 3.10+
- 32GB RAM recommended
- GPU recommended (MPS or CUDA)
- 500GB+ storage (depends on usage)

### Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| API Response Time | < 200ms | For status checks |
| File Upload | < 5s | For 50MB file |
| Processing Time | 2-3 min | For 4-minute song |
| Concurrent Jobs | 2-3 | Limited by GPU memory |
| Storage per Job | ~100MB | Varies by song length |

### Configuration Variables

```bash
# Server
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Storage
STORAGE_PATH=./storage
MAX_FILE_SIZE_MB=100
JOB_RETENTION_DAYS=7

# Processing
MAX_CONCURRENT_JOBS=3
ENABLE_GPU=true

# Database
DATABASE_URL=sqlite:///./api.db
# DATABASE_URL=postgresql://user:pass@localhost/musicapi

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/api.log
```

---

## 🚀 Deployment Strategy

### Development Deployment
```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install -r requirements-api.txt

# 2. Set up environment
cp .env.example .env
# Edit .env with your settings

# 3. Initialize database
alembic upgrade head

# 4. Run server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Deployment
```bash
# Build image
docker build -t music-transcription-api .

# Run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f api
```

### Production Deployment (with Nginx)
```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 600s;
    }
}
```

---

## 📈 Success Metrics

### Phase Completion Criteria
- [ ] Phase 1: Server runs, config loads, DB connects
- [ ] Phase 2: Jobs can be created and tracked
- [ ] Phase 3: All endpoints return correct responses
- [ ] Phase 4: Full pipeline executes successfully
- [ ] Phase 5: Files upload/download correctly
- [ ] Phase 6: Errors handled gracefully
- [ ] Phase 7: Tests pass, docs complete
- [ ] Phase 8: Production-ready deployment

### Quality Gates
- ✅ All unit tests pass
- ✅ Integration tests pass
- ✅ Code coverage > 80%
- ✅ No critical security issues
- ✅ API documentation complete
- ✅ Performance targets met
- ✅ Error handling comprehensive

---

## 🎯 Next Steps

### Immediate Actions (Week 1)
1. Review and approve this implementation plan
2. Set up development environment
3. Create Git branch: `feature/fastapi-backend`
4. Begin Phase 1: Project Setup

### Decision Points
- [ ] Choose job queue: BackgroundTasks vs Celery
- [ ] Choose database: SQLite vs PostgreSQL
- [ ] Decide on authentication: None vs API Key vs OAuth
- [ ] Choose deployment: Docker vs Traditional
- [ ] Decide on storage: Local vs S3

### Risk Mitigation
| Risk | Impact | Mitigation |
|------|--------|------------|
| Long processing times | High | Implement proper async handling, progress updates |
| Memory issues | High | Limit concurrent jobs, implement chunking |
| Storage costs | Medium | Implement cleanup, set retention policies |
| API downtime | Medium | Add health checks, monitoring, auto-restart |

---

## 📚 References

### Documentation to Create
- [ ] API_README.md - API usage guide
- [ ] DEPLOYMENT.md - Deployment instructions
- [ ] CONTRIBUTING.md - Development guidelines
- [ ] API_CHANGELOG.md - Version history

### External Resources
- FastAPI Documentation: https://fastapi.tiangolo.com/
- Pydantic Documentation: https://docs.pydantic.dev/
- SQLAlchemy Documentation: https://docs.sqlalchemy.org/
- Celery Documentation: https://docs.celeryq.dev/

---

**Document Version:** 1.0
**Last Updated:** 2026-01-31
**Next Review:** After Phase 4 completion

