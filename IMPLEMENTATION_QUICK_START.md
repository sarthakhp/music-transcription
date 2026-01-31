# FastAPI Backend - Quick Start Guide

## 🚀 Getting Started

This guide provides a quick reference for implementing the FastAPI backend for the music transcription pipeline.

---

## 📋 Pre-Implementation Checklist

- [ ] Review `FASTAPI_IMPLEMENTATION_PLAN.md` thoroughly
- [ ] Ensure Python 3.10+ is installed
- [ ] Verify existing pipeline works correctly
- [ ] Create new Git branch: `feature/fastapi-backend`
- [ ] Set up virtual environment for API development
- [ ] Install required tools (Docker, PostgreSQL optional)

---

## 🔧 Phase 1: Quick Setup (Day 1)

### Step 1: Create API Structure
```bash
mkdir -p api/{models,routes,services,workers,database,utils}
touch api/__init__.py
touch api/{models,routes,services,workers,database,utils}/__init__.py
```

### Step 2: Install Dependencies
```bash
# Create requirements-api.txt
cat > requirements-api.txt << EOF
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.0
pydantic-settings==2.1.0
sqlalchemy==2.0.25
alembic==1.13.1
python-multipart==0.0.6
aiofiles==23.2.1
python-magic==0.4.27
EOF

pip install -r requirements-api.txt
```

### Step 3: Create Basic FastAPI App
```python
# api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Music Transcription API",
    description="API for audio source separation and transcription",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Music Transcription API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### Step 4: Test Basic Server
```bash
python api/main.py
# Visit http://localhost:8000/docs
```

---

## 📊 Phase 2: Job Management (Days 2-3)

### Database Model
```python
# api/database/models.py
from sqlalchemy import Column, String, Integer, Float, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ProcessingStage(str, enum.Enum):
    SEPARATION = "separation"
    TRANSCRIPTION = "transcription"
    CHORDS = "chords"

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(String, primary_key=True)
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED)
    stage = Column(Enum(ProcessingStage), nullable=True)
    progress = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)
    input_filename = Column(String)
    file_size = Column(Integer)
```

### JobManager Service
```python
# api/services/job_manager.py
from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session
from api.database.models import Job, JobStatus, ProcessingStage

class JobManager:
    def __init__(self, db: Session):
        self.db = db
    
    def create_job(self, filename: str, file_size: int) -> Job:
        job = Job(
            id=str(uuid4()),
            input_filename=filename,
            file_size=file_size,
            status=JobStatus.QUEUED
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job
    
    def get_job(self, job_id: str) -> Job:
        return self.db.query(Job).filter(Job.id == job_id).first()
    
    def update_status(self, job_id: str, status: JobStatus, 
                     stage: ProcessingStage = None, progress: int = None):
        job = self.get_job(job_id)
        if job:
            job.status = status
            if stage:
                job.stage = stage
            if progress is not None:
                job.progress = progress
            if status == JobStatus.PROCESSING and not job.started_at:
                job.started_at = datetime.utcnow()
            if status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                job.completed_at = datetime.utcnow()
            self.db.commit()
```

---

## 🌐 Phase 3: API Endpoints (Days 4-5)

### Upload Endpoint
```python
# api/routes/transcription.py
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from api.services.job_manager import JobManager
from api.services.file_manager import FileManager
from api.workers.pipeline_worker import process_pipeline
from api.database.session import get_db

router = APIRouter(prefix="/api/v1", tags=["transcription"])

@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    # Validate file
    if not file.filename.endswith(('.mp3', '.wav', '.m4a')):
        raise HTTPException(400, "Invalid file format")
    
    # Create job
    job_manager = JobManager(db)
    job = job_manager.create_job(file.filename, file.size)
    
    # Save file
    file_manager = FileManager()
    input_path = await file_manager.save_upload(job.id, file)
    
    # Queue processing
    background_tasks.add_task(process_pipeline, job.id, input_path, db)
    
    return {
        "job_id": job.id,
        "status": job.status,
        "message": "Processing started"
    }

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job_manager = JobManager(db)
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(404, "Job not found")
    
    return {
        "job_id": job.id,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "created_at": job.created_at,
        "error_message": job.error_message
    }
```

---

## 🔄 Key Implementation Patterns

### 1. Dependency Injection
```python
# api/dependencies.py
from sqlalchemy.orm import Session
from api.database.session import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 2. Configuration Management
```python
# api/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    storage_path: str = "./storage"
    max_file_size_mb: int = 100
    max_concurrent_jobs: int = 3
    database_url: str = "sqlite:///./api.db"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### 3. Error Handling
```python
# api/utils/exceptions.py
from fastapi import HTTPException

class JobNotFoundException(HTTPException):
    def __init__(self, job_id: str):
        super().__init__(status_code=404, detail=f"Job {job_id} not found")

class InvalidAudioFileException(HTTPException):
    def __init__(self, message: str):
        super().__init__(status_code=400, detail=message)
```

---

## 📝 Development Workflow

1. **Start with Phase 1** - Get basic server running
2. **Implement Phase 2** - Add job management
3. **Build Phase 3** - Create API endpoints
4. **Integrate Phase 4** - Connect to existing pipeline
5. **Test thoroughly** - Each phase before moving forward
6. **Document as you go** - Update API docs

---

## 🧪 Testing Commands

```bash
# Run server in development
uvicorn api.main:app --reload

# Test upload
curl -X POST "http://localhost:8000/api/v1/transcribe" \
  -F "file=@test.mp3"

# Check status
curl "http://localhost:8000/api/v1/jobs/{job_id}"

# Run tests
pytest tests/

# Check coverage
pytest --cov=api tests/
```

---

## 📚 Next Steps

1. ✅ Review full implementation plan
2. ✅ Set up development environment
3. ✅ Start with Phase 1
4. ⏭️ Follow phases sequentially
5. ⏭️ Test after each phase
6. ⏭️ Document progress

For detailed information, see `FASTAPI_IMPLEMENTATION_PLAN.md`

