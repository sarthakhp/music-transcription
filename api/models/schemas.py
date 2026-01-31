from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from api.database.models import JobStatus, ProcessingStage


class JobCreate(BaseModel):
    pass


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    stage: Optional[ProcessingStage] = None
    progress: int
    
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    error_message: Optional[str] = None
    
    input_filename: str
    file_size: int
    
    duration: Optional[float] = None
    tempo_bpm: Optional[float] = None
    num_frames: Optional[int] = None
    num_chords: Optional[int] = None
    
    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    limit: int
    offset: int


class JobStatusResponse(BaseModel):
    id: str
    status: JobStatus
    stage: Optional[ProcessingStage] = None
    progress: int
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True


class TranscribeResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str = "Job created successfully"


class JobResultsResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int
    
    input_filename: str
    duration: Optional[float] = None
    tempo_bpm: Optional[float] = None
    
    stems: Optional[List[str]] = None
    frames_available: bool = False
    chords_available: bool = False
    
    num_frames: Optional[int] = None
    num_chords: Optional[int] = None
    
    processing_time: Optional[float] = None
    
    class Config:
        from_attributes = True


class StemInfo(BaseModel):
    name: str
    filename: str
    size_bytes: int
    download_url: str


class StemsListResponse(BaseModel):
    job_id: str
    stems: List[StemInfo]


class HealthResponse(BaseModel):
    status: str
    database: str
    storage: str
    active_jobs: int
    max_concurrent_jobs: int


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ProcessedFrame(BaseModel):
    time: float
    frequency: float
    confidence: float
    midi_pitch: Optional[float] = None
    is_voiced: bool


class FramesResponse(BaseModel):
    job_id: str
    metadata: dict
    processed_frames: List[ProcessedFrame]
    frame_count: int


class Chord(BaseModel):
    start_time: float
    end_time: float
    duration: float
    chord_label: str
    confidence: Optional[float] = None
    root: str = ""
    quality: str = ""
    bass: str = ""


class ChordsResponse(BaseModel):
    job_id: str
    chords: List[Chord]
    duration: float
    sample_rate: Optional[int] = None
    tempo_bpm: Optional[float] = None
    key_info: Optional[dict] = None
    num_chords: int


class DeleteJobResponse(BaseModel):
    job_id: str
    message: str = "Job deleted successfully"
    deleted: bool = True


class QueueStatusResponse(BaseModel):
    active_jobs: int
    max_concurrent_jobs: int
    can_accept_jobs: bool
    active_job_ids: List[str]

